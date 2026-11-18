// WinDoesNot USB stick writer for Windows 7 to 11 (C# 3.0 / .NET 3.5 compatible: it is compiled by Add-Type inside
// Windows PowerShell 2). Port of the raw ISO writer of the Windows app (Igloo.UsbWriter): fail-closed device checks,
// ISO hash checked BEFORE the first write, raw write, read-back verification. No GRUB patching, no repartitioning.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Management;
using System.Net;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using Microsoft.Win32.SafeHandles;

public sealed class WdnStickDrive {
    public int Index;
    public string Model;
    public long SizeBytes;
    public string DeviceId;
    public string Identity;
    public string Letters;
    public string MediaType;
    public bool Complete;
    public bool Removable;
    public bool Protected;
    public bool ContainsSource;
    public bool Foreign;
    public override string ToString() {
        return Model + "  -  " + (SizeBytes / 1000000000L).ToString(CultureInfo.InvariantCulture) + " GB" + (Letters.Length > 0 ? "  (" + Letters + ")" : "") + "  [Disk " + Index.ToString(CultureInfo.InvariantCulture) + "]";
    }
}

public static class WdnStick {
    const uint GENERIC_READ = 0x80000000, GENERIC_WRITE = 0x40000000, FILE_SHARE_RW = 3, OPEN_EXISTING = 3, FILE_FLAG_WRITE_THROUGH = 0x80000000;
    const uint IOCTL_STORAGE_GET_DEVICE_NUMBER = 0x002D1080, IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400;
    const uint IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x000700A0;
    const uint IOCTL_DISK_DELETE_DRIVE_LAYOUT = 0x0007C100, IOCTL_DISK_UPDATE_PROPERTIES = 0x00070140;
    const uint FSCTL_LOCK_VOLUME = 0x00090018, FSCTL_DISMOUNT_VOLUME = 0x00090020, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000;
    const int BusTypeUsb = 7;
    const int OneMiB = 1024 * 1024;
    public const long ReserveBytes = 256L * 1024 * 1024;
    public const long MaxStickBytes = 256L * 1000 * 1000 * 1000;
    public const long MinStickBytes = 6L * 1000 * 1000 * 1000; // the ISO is about 5.2 GB; smaller devices are never offered

    // ---- progress shared with the UI thread (polled by a timer) ----
    public static volatile string Phase = "";
    public static long Done;
    public static long Total;
    public static volatile string Error = "";
    public static volatile bool Finished;
    public static volatile bool Cancel;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr sa, uint disposition, uint flags, IntPtr template);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool DeviceIoControl(SafeFileHandle h, uint code, byte[] inBuf, int inSize, byte[] outBuf, int outSize, out int returned, IntPtr overlapped);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool FlushFileBuffers(SafeFileHandle h);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr FindFirstVolume(StringBuilder name, uint len);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool FindNextVolume(IntPtr find, StringBuilder name, uint len);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool FindVolumeClose(IntPtr find);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool GetVolumePathName(string file, StringBuilder mount, uint len);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool GetVolumeNameForVolumeMountPoint(string mount, StringBuilder volume, uint len);

    public static bool IsAdministrator() {
        WindowsIdentity id = WindowsIdentity.GetCurrent();
        try { return id.IsSystem || new WindowsPrincipal(id).IsInRole(WindowsBuiltInRole.Administrator); }
        finally { id.Dispose(); }
    }

    // ---------------------------------------------------------------- inventory
    static List<ManagementObject> Associators(string source, string assoc, string result) {
        List<ManagementObject> list = new List<ManagementObject>();
        try {
            using (ManagementObjectSearcher s = new ManagementObjectSearcher("ASSOCIATORS OF {" + source + "} WHERE AssocClass=" + assoc + " ResultClass=" + result)) {
                foreach (ManagementObject o in s.Get()) list.Add(o);
            }
        } catch (ManagementException ex) { if (ex.ErrorCode != ManagementStatus.NotFound) throw; list.Clear(); }
        return list;
    }

    static int? DiskIndexOfLetter(string letter) {
        foreach (ManagementObject part in Associators("Win32_LogicalDisk.DeviceID='" + letter + "'", "Win32_LogicalDiskToPartition", "Win32_DiskPartition")) {
            using (part) {
                foreach (ManagementObject disk in Associators("Win32_DiskPartition.DeviceID='" + part["DeviceID"] + "'", "Win32_DiskDriveToDiskPartition", "Win32_DiskDrive")) {
                    using (disk) { if (disk["Index"] != null) return Convert.ToInt32(disk["Index"], CultureInfo.InvariantCulture); }
                }
            }
        }
        return null;
    }

    static string LetterOf(string path) {
        if (string.IsNullOrEmpty(path)) return null;
        string root = Path.GetPathRoot(Path.GetFullPath(path));
        if (string.IsNullOrEmpty(root) || root.StartsWith(@"\\", StringComparison.Ordinal)) return null;
        return root.TrimEnd('\\');
    }

    /// <summary>Fresh inventory of USB disks. Anything unclear makes a drive "incomplete" (never offered).</summary>
    public static List<WdnStickDrive> ReadDrives(string isoPath) {
        List<WdnStickDrive> result = new List<WdnStickDrive>();
        string sysRoot = Path.GetPathRoot(Environment.SystemDirectory);
        string systemLetter = sysRoot.TrimEnd('\\');
        string isoLetter = LetterOf(isoPath);
        string appLetter = LetterOf(AppDomain.CurrentDomain.BaseDirectory);
        int? systemDisk = null;
        bool systemKnown = true;
        try { systemDisk = DiskIndexOfLetter(systemLetter); } catch (ManagementException) { systemKnown = false; }
        if (systemDisk == null) systemKnown = false;

        // Optional second source (Windows 8 and newer): boot/system flag and bus type of every disk.
        Dictionary<int, bool[]> storage = null; // [isBoot, isSystem, isUsb]
        bool storageAvailable = false;
        try {
            Dictionary<int, bool[]> map = new Dictionary<int, bool[]>();
            using (ManagementObjectSearcher d = new ManagementObjectSearcher(@"root\Microsoft\Windows\Storage", "SELECT Number, BusType, IsBoot, IsSystem FROM MSFT_Disk")) {
                foreach (ManagementObject o in d.Get()) {
                    using (o) {
                        if (o["Number"] == null) continue;
                        map[Convert.ToInt32(o["Number"], CultureInfo.InvariantCulture)] = new bool[] {
                            o["IsBoot"] is bool && (bool)o["IsBoot"], o["IsSystem"] is bool && (bool)o["IsSystem"],
                            Convert.ToInt32(o["BusType"] ?? 0, CultureInfo.InvariantCulture) == BusTypeUsb };
                    }
                }
            }
            storage = map; storageAvailable = true;
        } catch (ManagementException) { storageAvailable = false; }

        using (ManagementObjectSearcher s = new ManagementObjectSearcher("SELECT DeviceID, Index, Model, Size, MediaType, PNPDeviceID, SerialNumber FROM Win32_DiskDrive WHERE InterfaceType='USB'")) {
            foreach (ManagementObject disk in s.Get()) {
                using (disk) {
                    WdnStickDrive d = new WdnStickDrive();
                    d.DeviceId = disk["DeviceID"] == null ? "" : disk["DeviceID"].ToString();
                    d.Complete = systemKnown && d.DeviceId.Length > 0 && disk["Index"] != null;
                    d.Index = d.Complete ? Convert.ToInt32(disk["Index"], CultureInfo.InvariantCulture) : -1;
                    long size; long.TryParse(disk["Size"] == null ? "" : disk["Size"].ToString(), NumberStyles.None, CultureInfo.InvariantCulture, out size);
                    d.SizeBytes = size;
                    d.Model = disk["Model"] == null ? "USB" : disk["Model"].ToString();
                    d.MediaType = disk["MediaType"] == null ? "" : disk["MediaType"].ToString();
                    string pnp = disk["PNPDeviceID"] == null ? "" : disk["PNPDeviceID"].ToString();
                    string serial = disk["SerialNumber"] == null ? "" : disk["SerialNumber"].ToString().Trim();
                    d.Identity = pnp.Length == 0 ? null : pnp + "|" + serial + "|" + size.ToString(CultureInfo.InvariantCulture);
                    d.Protected = d.Index == systemDisk;
                    List<string> letters = new List<string>();
                    try {
                        string esc = d.DeviceId.Replace(@"\", @"\\");
                        foreach (ManagementObject part in Associators("Win32_DiskDrive.DeviceID='" + esc + "'", "Win32_DiskDriveToDiskPartition", "Win32_DiskPartition")) {
                            using (part) {
                                string ptype = part["Type"] == null ? "" : part["Type"].ToString();
                                if (ptype.IndexOf("Logical Disk Manager", StringComparison.OrdinalIgnoreCase) >= 0 || ptype.IndexOf("Storage Spaces", StringComparison.OrdinalIgnoreCase) >= 0) d.Foreign = true;
                                foreach (ManagementObject logical in Associators("Win32_DiskPartition.DeviceID='" + part["DeviceID"] + "'", "Win32_LogicalDiskToPartition", "Win32_LogicalDisk")) {
                                    using (logical) {
                                        string letter = logical["DeviceID"] == null ? null : logical["DeviceID"].ToString();
                                        if (!string.IsNullOrEmpty(letter)) {
                                            letters.Add(letter);
                                            if (string.Equals(letter, systemLetter, StringComparison.OrdinalIgnoreCase) || Directory.Exists(letter + "\\Windows\\System32")) d.Protected = true;
                                        }
                                    }
                                }
                            }
                        }
                    } catch (ManagementException) { d.Complete = false; }
                    catch (IOException) { d.Complete = false; }
                    catch (UnauthorizedAccessException) { d.Complete = false; }
                    d.Letters = string.Join(", ", letters.ToArray());
                    d.ContainsSource = (isoLetter != null && letters.Contains(isoLetter)) || (appLetter != null && letters.Contains(appLetter));
                    if (d.Foreign) d.Protected = true;
                    if (storageAvailable) {
                        bool[] st;
                        if (!storage.TryGetValue(d.Index, out st) || !st[2]) d.Complete = false;
                        else if (st[0] || st[1]) d.Protected = true;
                    }
                    // "Removable Media" for sticks; some sticks report "External hard disk media": accepted only up to a stick size.
                    d.Removable = d.MediaType.IndexOf("Removable", StringComparison.OrdinalIgnoreCase) >= 0
                        || (d.MediaType.IndexOf("External", StringComparison.OrdinalIgnoreCase) >= 0 && size > 0 && size <= MaxStickBytes);
                    result.Add(d);
                }
            }
        }
        return result;
    }

    /// <summary>Drives that may be offered (the ISO size is checked again before writing).</summary>
    public static List<WdnStickDrive> OfferedDrives(string isoPath) {
        List<WdnStickDrive> offered = new List<WdnStickDrive>();
        foreach (WdnStickDrive d in ReadDrives(isoPath)) {
            if (d.Complete && d.Removable && !d.Protected && !d.ContainsSource && d.Identity != null && d.SizeBytes >= MinStickBytes && d.SizeBytes <= MaxStickBytes) offered.Add(d);
        }
        return offered;
    }

    // ---------------------------------------------------------------- device queries on a handle
    static int QueryDeviceNumber(SafeFileHandle h) {
        byte[] o = new byte[12]; int n;
        if (!DeviceIoControl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, null, 0, o, o.Length, out n, IntPtr.Zero) || n < 8) throw new Win32Exception(Marshal.GetLastWin32Error(), "IOCTL_STORAGE_GET_DEVICE_NUMBER failed. Nothing was written.");
        return BitConverter.ToInt32(o, 4);
    }
    static int QueryBusType(SafeFileHandle h) {
        byte[] q = new byte[12]; byte[] o = new byte[1024]; int n;
        if (!DeviceIoControl(h, IOCTL_STORAGE_QUERY_PROPERTY, q, q.Length, o, o.Length, out n, IntPtr.Zero) || n < 32) throw new Win32Exception(Marshal.GetLastWin32Error(), "IOCTL_STORAGE_QUERY_PROPERTY failed. Nothing was written.");
        return BitConverter.ToInt32(o, 28);
    }
    static long QueryLength(SafeFileHandle h) {
        byte[] o = new byte[8]; int n;
        if (!DeviceIoControl(h, IOCTL_DISK_GET_LENGTH_INFO, null, 0, o, o.Length, out n, IntPtr.Zero) || n < 8) throw new Win32Exception(Marshal.GetLastWin32Error(), "IOCTL_DISK_GET_LENGTH_INFO failed. Nothing was written.");
        return BitConverter.ToInt64(o, 0);
    }
    static int QueryBytesPerSector(SafeFileHandle h) {
        byte[] o = new byte[256]; int n;
        if (!DeviceIoControl(h, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, null, 0, o, o.Length, out n, IntPtr.Zero) || n < 24) throw new Win32Exception(Marshal.GetLastWin32Error(), "IOCTL_DISK_GET_DRIVE_GEOMETRY_EX failed. Nothing was written.");
        return BitConverter.ToInt32(o, 20);
    }

    // 0 = not on the disk, 1 = on the disk, 2 = spans other disks, 3 = unknown
    static int VolumeLocation(SafeFileHandle volume, int diskIndex) {
        byte[] o = new byte[8 + 32 * 24]; int n;
        if (!DeviceIoControl(volume, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, null, 0, o, o.Length, out n, IntPtr.Zero))
            return Marshal.GetLastWin32Error() == 234 ? 2 : 3;
        if (n < 8) return 3;
        int count = Math.Min(BitConverter.ToInt32(o, 0), 32);
        bool on = false, elsewhere = false;
        for (int i = 0; i < count; i++) { if (BitConverter.ToInt32(o, 8 + i * 24) == diskIndex) on = true; else elsewhere = true; }
        return !on ? 0 : (elsewhere ? 2 : 1);
    }

    static bool IsPathOnDisk(string path, int diskIndex) {
        string full = Path.GetFullPath(path);
        if (full.StartsWith(@"\\", StringComparison.Ordinal) && !full.StartsWith(@"\\?\", StringComparison.Ordinal)) return false;
        StringBuilder mount = new StringBuilder(1024); StringBuilder volume = new StringBuilder(64);
        if (!GetVolumePathName(full, mount, (uint)mount.Capacity) || !GetVolumeNameForVolumeMountPoint(mount.ToString(), volume, (uint)volume.Capacity)) return true;
        using (SafeFileHandle h = CreateFile(volume.ToString().TrimEnd('\\'), 0, FILE_SHARE_RW, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero)) {
            return h.IsInvalid || VolumeLocation(h, diskIndex) != 0;
        }
    }

    static List<SafeFileHandle> LockVolumes(int diskIndex) {
        List<SafeFileHandle> held = new List<SafeFileHandle>();
        try {
            List<string> names = new List<string>();
            StringBuilder buf = new StringBuilder(260);
            IntPtr find = FindFirstVolume(buf, (uint)buf.Capacity);
            if (find == new IntPtr(-1)) throw new Win32Exception(Marshal.GetLastWin32Error(), "FindFirstVolume failed. Nothing was written.");
            try {
                do { names.Add(buf.ToString()); } while (FindNextVolume(find, buf, (uint)buf.Capacity));
                int err = Marshal.GetLastWin32Error();
                if (err != 18) throw new Win32Exception(err, "FindNextVolume failed. Nothing was written.");
            } finally { FindVolumeClose(find); }
            foreach (string name in names) {
                string path = name.TrimEnd('\\');
                SafeFileHandle h = CreateFile(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_RW, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
                bool keep = false;
                try {
                    if (h.IsInvalid) continue;
                    int loc = VolumeLocation(h, diskIndex);
                    if (loc == 0 || loc == 3) continue;
                    if (loc == 2) throw new InvalidOperationException("A volume on this drive spans another disk (dynamic disk). Nothing was written.");
                    bool locked = false; int n;
                    for (int attempt = 0; attempt < 20 && !locked; attempt++) {
                        locked = DeviceIoControl(h, FSCTL_LOCK_VOLUME, null, 0, null, 0, out n, IntPtr.Zero);
                        if (!locked) Thread.Sleep(250);
                    }
                    if (!locked) throw new IOException("A volume on the USB drive is in use (" + path + "). Close Explorer windows and programs using the stick, then try again. Nothing was written.");
                    if (!DeviceIoControl(h, FSCTL_DISMOUNT_VOLUME, null, 0, null, 0, out n, IntPtr.Zero)) throw new Win32Exception(Marshal.GetLastWin32Error(), "Could not dismount " + path + ". Nothing was written.");
                    held.Add(h); keep = true;
                } finally { if (!keep) h.Dispose(); }
            }
            return held;
        } catch { foreach (SafeFileHandle h in held) h.Dispose(); throw; }
    }

    static string Hex(byte[] bytes) { StringBuilder sb = new StringBuilder(bytes.Length * 2); foreach (byte b in bytes) sb.Append(b.ToString("X2", CultureInfo.InvariantCulture)); return sb.ToString(); }

    public static string Sha256OfFile(string path) {
        using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20))
        using (SHA256 sha = SHA256.Create()) {
            byte[] chunk = new byte[4 * OneMiB]; int n;
            while ((n = fs.Read(chunk, 0, chunk.Length)) > 0) sha.TransformBlock(chunk, 0, n, null, 0);
            sha.TransformFinalBlock(new byte[0], 0, 0);
            return Hex(sha.Hash);
        }
    }

    static int RoundUp(int bytes) { return bytes == 0 ? 0 : ((bytes + 4095) / 4096) * 4096; }

    static void WriteZeros(FileStream dev, long offset, long count) {
        byte[] zeros = new byte[OneMiB]; dev.Position = offset;
        while (count > 0) { int n = (int)Math.Min(zeros.Length, count); dev.Write(zeros, 0, n); count -= n; }
    }

    // ---------------------------------------------------------------- the write
    /// <summary>Writes the ISO raw to the selected drive. Throws (with "Nothing was written." where applicable) on every refusal.</summary>
    public static void WriteIso(WdnStickDrive drive, string isoPath, string expectedSha256) {
        if (drive == null) throw new ArgumentNullException("drive");
        if (expectedSha256 == null || expectedSha256.Length != 64) throw new ArgumentException("A SHA-256 hex string is required.");
        if (!IsAdministrator()) throw new UnauthorizedAccessException("Writing to a physical drive requires administrator rights. Please restart the program as administrator.");
        Done = 0; Total = 0; Finished = false; Error = ""; Cancel = false;
        using (FileStream src = new FileStream(isoPath, FileMode.Open, FileAccess.Read, FileShare.Read, 1, FileOptions.SequentialScan)) {
            long isoSize = src.Length; Total = isoSize;
            using (SafeFileHandle disk = CreateFile(drive.DeviceId, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_RW, IntPtr.Zero, OPEN_EXISTING, FILE_FLAG_WRITE_THROUGH, IntPtr.Zero)) {
                if (disk.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error(), "Cannot open " + drive.DeviceId + ". Nothing was written.");
                // identify the handle, then re-inventory, then identify again
                if (QueryDeviceNumber(disk) != drive.Index || QueryBusType(disk) != BusTypeUsb) throw new InvalidOperationException("The opened device is not the selected USB drive. Nothing was written.");
                WdnStickDrive current = null;
                foreach (WdnStickDrive c in ReadDrives(isoPath)) { if (c.Index == drive.Index) { if (current != null) throw new InvalidOperationException("Ambiguous drive list. Nothing was written."); current = c; } }
                if (current == null) throw new InvalidOperationException("The selected USB drive is no longer present. Nothing was written.");
                if (drive.Identity == null || !string.Equals(drive.Identity, current.Identity, StringComparison.OrdinalIgnoreCase) || current.SizeBytes != drive.SizeBytes
                    || !string.Equals(current.DeviceId, drive.DeviceId, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("The USB drive changed since it was selected. Nothing was written.");
                if (!(current.Complete && current.Removable && !current.Protected && !current.ContainsSource && current.SizeBytes <= MaxStickBytes && current.SizeBytes >= isoSize + ReserveBytes))
                    throw new InvalidOperationException("This drive is not allowed as a target (system disk, not removable, too small or too large, or the state could not be determined). Nothing was written.");
                int sector = QueryBytesPerSector(disk);
                if (sector != 512) throw new NotSupportedException("This USB device uses " + sector.ToString(CultureInfo.InvariantCulture) + "-byte sectors; the installer image only boots from 512-byte-sector sticks. Please use another stick. Nothing was written.");
                long diskLength = QueryLength(disk);
                if (QueryDeviceNumber(disk) != drive.Index || diskLength < isoSize + ReserveBytes) throw new InvalidOperationException("The USB drive changed or is too small. Nothing was written.");
                if (IsPathOnDisk(isoPath, drive.Index)) throw new InvalidOperationException("The installer image is stored on the selected USB drive. Nothing was written.");

                // check the image BEFORE anything on the stick is touched
                Phase = "check"; Done = 0;
                using (SHA256 pre = SHA256.Create()) {
                    byte[] chunk = new byte[4 * OneMiB]; long pos = 0;
                    while (pos < isoSize) {
                        if (Cancel) throw new OperationCanceledException("Cancelled. Nothing was written.");
                        int n = src.Read(chunk, 0, (int)Math.Min(chunk.Length, isoSize - pos));
                        if (n <= 0) throw new EndOfStreamException("The installer image ended early. Nothing was written.");
                        pre.TransformBlock(chunk, 0, n, null, 0); pos += n; Done = pos;
                    }
                    pre.TransformFinalBlock(new byte[0], 0, 0);
                    if (!string.Equals(Hex(pre.Hash), expectedSha256, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("The installer image does not match its expected checksum. Nothing was written.");
                    src.Position = 0;
                }

                List<SafeFileHandle> held = LockVolumes(drive.Index);
                try {
                    using (FileStream dev = new FileStream(disk, FileAccess.ReadWrite, 1, false)) {
                        bool touched = false, done = false;
                        try {
                            int n0; DeviceIoControl(disk, IOCTL_DISK_DELETE_DRIVE_LAYOUT, null, 0, null, 0, out n0, IntPtr.Zero);
                            touched = true;
                            long tail = (diskLength - OneMiB) & ~4095L;
                            WriteZeros(dev, tail, diskLength - tail);
                            Phase = "write"; Done = 0;
                            byte[] buffer = new byte[4 * OneMiB]; dev.Position = 0;
                            for (long pos = 0; pos < isoSize; ) {
                                if (Cancel) throw new OperationCanceledException("Cancelled. The stick was cleared and is not usable.");
                                int want = (int)Math.Min(buffer.Length, isoSize - pos);
                                int got = 0; while (got < want) { int r = src.Read(buffer, got, want - got); if (r <= 0) throw new EndOfStreamException("The installer image ended early."); got += r; }
                                int toWrite = RoundUp(want);
                                if (toWrite != want) Array.Clear(buffer, want, toWrite - want);
                                dev.Write(buffer, 0, toWrite);
                                pos += want; Done = pos;
                            }
                            dev.Flush(); FlushFileBuffers(disk);
                            Phase = "verify"; Done = 0;
                            byte[] back = new byte[buffer.Length]; src.Position = 0; dev.Position = 0;
                            for (long pos = 0; pos < isoSize; ) {
                                if (Cancel) throw new OperationCanceledException("Cancelled. The stick was cleared and is not usable.");
                                int want = (int)Math.Min(buffer.Length, isoSize - pos);
                                int got = 0; while (got < want) { int r = src.Read(buffer, got, want - got); if (r <= 0) throw new EndOfStreamException("The installer image ended early."); got += r; }
                                int wantDev = RoundUp(want); int gotDev = 0;
                                while (gotDev < wantDev) { int r = dev.Read(back, gotDev, wantDev - gotDev); if (r <= 0) throw new EndOfStreamException("The stick ended early while verifying."); gotDev += r; }
                                for (int i = 0; i < want; i++) { if (buffer[i] != back[i]) throw new IOException("Verification failed at offset " + (pos + i).ToString(CultureInfo.InvariantCulture) + ". The stick was cleared; try another stick."); }
                                pos += want; Done = pos;
                            }
                            int n1; DeviceIoControl(disk, IOCTL_DISK_UPDATE_PROPERTIES, null, 0, null, 0, out n1, IntPtr.Zero);
                            done = true;
                        } finally {
                            if (touched && !done) { try { WriteZeros(dev, 0, OneMiB); dev.Flush(); } catch (IOException) { } catch (UnauthorizedAccessException) { } catch (NotSupportedException) { } }
                        }
                    }
                } finally { foreach (SafeFileHandle h in held) h.Dispose(); }
            }
        }
        Phase = "done";
    }

    /// <summary>Runs WriteIso on a background thread; poll Phase/Done/Total/Error/Finished.</summary>
    public static void StartWrite(WdnStickDrive drive, string isoPath, string expectedSha256) {
        Phase = "check"; Done = 0; Total = 0; Error = ""; Finished = false; Cancel = false;
        Thread t = new Thread(delegate() {
            try { WriteIso(drive, isoPath, expectedSha256); }
            catch (Exception ex) { Error = ex.Message; }
            finally { Finished = true; }
        });
        t.IsBackground = true; t.Start();
    }

    // ---------------------------------------------------------------- download
    /// <summary>Downloads a file over HTTPS with progress (no resume: .NET 3.5 cannot range-request beyond 2 GB). TLS 1.2 is requested when the runtime knows it.</summary>
    public static void StartDownload(string url, string target, string expectedSha256) {
        Phase = "download"; Done = 0; Total = 0; Error = ""; Finished = false; Cancel = false;
        Thread t = new Thread(delegate() {
            try { Download(url, target, expectedSha256); }
            catch (Exception ex) { Error = ex.Message; }
            finally { Finished = true; }
        });
        t.IsBackground = true; t.Start();
    }

    static void EnableTls() {
        try { ServicePointManager.SecurityProtocol = (SecurityProtocolType)(3072 | 768 | 192); } // TLS 1.2 | 1.1 | 1.0
        catch (NotSupportedException) { }
        catch (ArgumentException) { }
    }

    public static string FetchText(string url) {
        EnableTls();
        HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
        req.UserAgent = "WinDoesNot-Setup"; req.Timeout = 20000;
        using (WebResponse resp = req.GetResponse())
        using (StreamReader r = new StreamReader(resp.GetResponseStream(), Encoding.UTF8)) { return r.ReadToEnd(); }
    }

    static void Download(string url, string target, string expectedSha256) {
        if (!url.StartsWith("https://", StringComparison.OrdinalIgnoreCase) && !url.StartsWith("http://127.", StringComparison.Ordinal) && !url.StartsWith("http://10.0.2.2", StringComparison.Ordinal))
            throw new InvalidOperationException("Only HTTPS downloads are allowed.");
        EnableTls();
        string partial = target + ".partial";
        HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
        req.UserAgent = "WinDoesNot-Setup"; req.Timeout = 30000; req.ReadWriteTimeout = 30000; req.AllowAutoRedirect = true;
        using (WebResponse resp = req.GetResponse()) {
            HttpWebResponse http = (HttpWebResponse)resp;
            Total = http.ContentLength;
            using (Stream input = resp.GetResponseStream())
            using (FileStream output = new FileStream(partial, FileMode.Create, FileAccess.Write, FileShare.Read)) {
                Done = 0;
                byte[] buf = new byte[256 * 1024]; int n;
                while ((n = input.Read(buf, 0, buf.Length)) > 0) {
                    if (Cancel) throw new OperationCanceledException("Download cancelled.");
                    output.Write(buf, 0, n); Done += n;
                }
            }
        }
        Phase = "hash"; Done = 0;
        string got = Sha256OfFile(partial);
        if (!string.Equals(got, expectedSha256, StringComparison.OrdinalIgnoreCase)) { try { File.Delete(partial); } catch (IOException) { } throw new InvalidDataException("The downloaded file does not match its checksum. It was deleted; try again."); }
        if (File.Exists(target)) File.Delete(target);
        File.Move(partial, target);
        Phase = "downloaded";
    }
}
