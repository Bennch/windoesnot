using System.Reflection;
using System.Text.Json;
using Igloo.Core.Abstractions;
using Igloo.UsbWriter;
using Microsoft.Extensions.Logging.Abstractions;

var service = new UsbWriterService(NullLogger<UsbWriterService>.Instance);
try
{
    var drives = await service.EnumerateDrivesAsync();
    if (args.Length == 1 && args[0] == "list")
    {
        var inventory = typeof(UsbWriterService).Assembly.GetType("Igloo.UsbWriter.UsbInventory")!;
        var entries = inventory.GetMethod("Read", BindingFlags.Static | BindingFlags.NonPublic)!.Invoke(null, new object?[] { null, AppContext.BaseDirectory });
        Console.WriteLine(JsonSerializer.Serialize(new { drives, inventory = entries }, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
    if (args.Length < 3) throw new ArgumentException("list | write <index> <iso> [identity] | write-wrong-identity <index> <iso> | write-system-disk <index> <iso>");
    int index = int.Parse(args[1]);
    var drive = drives.FirstOrDefault(d => d.DriveIndex == index);
    if (args[0] == "write-system-disk")
        drive = new UsbDriveInfo(index, "forced", 16L * 1024 * 1024 * 1024, @"\\.\PHYSICALDRIVE" + index, "forced");
    else if (drive is null)
        drive = new UsbDriveInfo(index, "forced", 16L * 1024 * 1024 * 1024, @"\\.\PHYSICALDRIVE" + index, "forced");
    if (args[0] == "write-wrong-identity") drive = drive with { Identity = "intentionally wrong" };
    else if (args[0] == "write" && args.Length > 3) drive = drive with { Identity = args[3] };
    else if (args[0] != "write" && args[0] != "write-system-disk") throw new ArgumentException("Unknown command");
    await service.WriteAsync(drive, args[2], "", new InlineProgress());
    return 0;
}
catch (Exception ex) { Console.Error.WriteLine(ex.ToString()); return 1; }

sealed class InlineProgress : IProgress<UsbWriteProgress>
{
    public void Report(UsbWriteProgress value) => Console.WriteLine(JsonSerializer.Serialize(value));
}
