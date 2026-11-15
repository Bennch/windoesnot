# Linux-zu-Linux-Umzug: Entwurf

## Quelle und Schutz

Quellen sind andere Linux-Dateisysteme auf lokalen Blockgeräten (ext4, XFS,
Btrfs); LUKS wird nur nach Passworteingabe per stdin und ausschließlich lesend
geöffnet. Mounts erfolgen mit ro,nosuid,nodev,noexec, bei ext4 zusätzlich
noload, bei XFS norecovery; Btrfs erhält die geeigneten Optionen für eine
lesende Einbindung. Btrfs-Subvolumes @ und @home sowie separate Home-Partitionen
müssen ausdrücklich erkannt und eingebunden werden. Unbekannte oder nicht
vollständig erreichbare Quellen führen zu einer sichtbaren Warnung und dürfen
nicht als vollständiger Spiegel gelten. Das Passwort wird weder protokolliert
noch dauerhaft gespeichert.

Vor jeder Partitionierung muss der Guard anhand einer vollständigen Liste aller
Schreibziele und ihrer Blockgeräte-Abstammung beweisen, dass die Quelle nicht
betroffen ist. „Parallel installieren“ ist nur sicher, soweit der konkrete
Partitionierungsplan die Quelle und alle für sie nötigen Geräte erhält. Bei
unbekannter Identität oder unvollständigem Plan wird gesperrt. Dieselbe Identität
muss unmittelbar vor Mount und Kopieren erneut geprüft werden; Gerätepfade
allein sind keine Identität.

## Inhalt und Ziel

Alle ausgewählten Benutzerhomes werden vollständig einschließlich versteckter
Dateien, Browserprofilen, SSH/GnuPG, Shell-Historie, Flatpak-Nutzerdaten,
Spielen, Benutzer-Cron und systemd-Timern übernommen. Symlinks werden als
Links erhalten, aber nie verfolgt; Hardlinks, ACLs und xattrs bleiben erhalten.
Mountgrenzen und separat eingebundene Dateisysteme werden explizit erkannt:
Sie dürfen nicht stillschweigend als kopiert gelten. Mehrere Quellbenutzer
benötigen eine explizite Zuordnung zu Zielbenutzern bzw. eigene Archivpfade;
ein Überschreiben fremder Homes ist ausgeschlossen.

WinDoesNot-verwaltete Konfigurationen (unter anderem hypr, quickshell, swaync,
ghostty, gtk-3.0, gtk-4.0, fish und alle weiteren unter desktop/config
verwalteten Pfade) werden unverändert unter
`~/Umzug-<Quelle>/original/<relativer Pfad>` archiviert. Auch Zielkonflikte
werden dort erhalten, nicht überschrieben. Der Bericht nennt Quelle und
Wiederherstellung. `/etc` wird vollständig nach
`/var/lib/windoesnot/mirror/<datum>/etc-alt` archiviert; nur NetworkManager-
Verbindungen werden kontrolliert mit Modus 600 wiederhergestellt. SSH-Hostkeys
werden nicht aktiviert. fstab, crypttab, machine-id, Bootloader, Kernel,
initramfs, mkinitcpio, pacman-Keyring und Hardware-Treiberkonfiguration werden
nicht aktiviert, weil sie Geräteidentität, Bootfähigkeit, Vertrauen oder die
Hardware des neuen Systems betreffen. Aktivierte Dienste werden nur aufgelistet.
Auch diese Dateien bleiben im Archiv erhalten.

Arch-Paketnamen stammen aus lokalen pacman-desc-Dateien: explizit installierte
Pakete haben INSTALL REASON 0; Fremdpakete sind lokal installiert, aber in
keiner verfügbaren Sync-Datenbank enthalten. Fehlen Sync-Datenbanken, ist die
Fremdpaketklassifikation unbekannt, nicht leer. Debian-Paketstatus und apt-
Markierungen liefern lediglich eine manuelle Paketliste zur Anzeige und
gegebenenfalls Namenszuordnung. System- und Benutzer-Flatpak-Apps werden
aufgelistet. Ein späterer Oneshot installiert nur validierte Repo-Namen einzeln
mit pacman --needed und Flatpak-Apps einzeln; Fremd- und Debian-Pakete bleiben
Hinweise. Kernel, Bootloader und Treiber stehen auf einer konservativen
Denylist. Status und Bericht müssen Wiederholungen und Teilfehler korrekt
abbilden; Benachrichtigungen benötigen eine erreichbare Benutzersitzung.

## Integrität und Grenzen

Das Manifest (Schema 1, kind linux) enthält Systemname aus PRETTY_NAME,
Benutzer und Größen, Paketlisten, Dienste und Warnungen. Es ist untrusted input:
alle Pfade werden erneut unter der eingebundenen Quelle geprüft, Zielpfade ohne
Symlink-Umleitung geöffnet und Quelle/Ziel dürfen sich nicht überlappen. Vor
rsync -aHAX --numeric-ids werden Platz und Zielkonflikte geprüft; UID/GID werden
explizit zugeordnet. Fortschritt ist JSON; konfigurierbare vollständige oder
stichprobenartige SHA-256- und Größenprüfung erfasst Abweichungen. Unlesbare
Dateien, Sonderdateien, inkonsistente Snapshots und veränderliche Quelldaten
müssen als Fehler ausgewiesen werden. Ein vollständiger Spiegel kann nur für
lesbare, eingebundene Daten mit ausreichendem Platz und erfolgreich überprüfter
Kopie zugesichert werden; Dateisystem-Snapshots sind für Konsistenz bevorzugt.
