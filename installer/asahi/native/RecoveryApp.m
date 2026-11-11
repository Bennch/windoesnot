// SPDX-License-Identifier: MIT
// AppKit only: no Electron, browser, Python or downloaded runtime in Recovery.
#import <Cocoa/Cocoa.h>
#include <util.h>
#include <termios.h>
#include <sys/select.h>
#include <sys/wait.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
static BOOL previewMode = NO;

static int Bridge(const char *script) {
    if (geteuid() != 0) return 77;
    int master;
    setenv("WINDOESNOT_GUI", "1", 1);
    signal(SIGPIPE, SIG_IGN);
    pid_t child = forkpty(&master, NULL, NULL, NULL);
    if (child < 0) return 78;
    if (!child) {
        struct termios attrs;
        if (!tcgetattr(0, &attrs)) { attrs.c_lflag &= ~(ECHO | ECHONL); tcsetattr(0, TCSANOW, &attrs); }
        execl("/bin/sh", "sh", script, (char *)NULL);
        _exit(78);
    }
    BOOL inputOpen = YES;
    char buffer[8192];
    for (;;) {
        fd_set set; FD_ZERO(&set); FD_SET(master, &set); if (inputOpen) FD_SET(0, &set);
        if (select(master + 1, &set, NULL, NULL, NULL) < 0) continue;
        if (inputOpen && FD_ISSET(0, &set)) {
            ssize_t count = read(0, buffer, sizeof(buffer));
            if (count > 0) {
                ssize_t offset = 0;
                while (offset < count) { ssize_t n = write(master, buffer + offset, count - offset); if (n <= 0) break; offset += n; }
            } else inputOpen = NO; // Never kill a boot-policy operation on GUI loss.
        }
        if (FD_ISSET(master, &set)) {
            ssize_t count = read(master, buffer, sizeof(buffer));
            if (count <= 0) break;
            ssize_t offset = 0;
            while (offset < count) { ssize_t n = write(1, buffer + offset, count - offset); if (n <= 0) break; offset += n; }
        }
    }
    close(master);
    int status; waitpid(child, &status, 0);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

@interface RecoveryApp : NSObject <NSApplicationDelegate, NSWindowDelegate>
@property (nonatomic, strong) NSWindow *window;
@property (nonatomic, strong) NSTextField *heading;
@property (nonatomic, strong) NSTextField *body;
@property (nonatomic, strong) NSTextField *prompt;
@property (nonatomic, strong) NSTextField *answer;
@property (nonatomic, strong) NSSecureTextField *password;
@property (nonatomic, strong) NSButton *button;
@property (nonatomic, strong) NSPopUpButton *language;
@property (nonatomic, strong) NSProgressIndicator *spinner;
@property (nonatomic, strong) NSTextView *details;
@property (nonatomic, strong) NSTask *task;
@property (nonatomic, strong) NSFileHandle *input;
@property (nonatomic, strong) NSMutableData *buffer;
@property (nonatomic, strong) NSString *phase;
@property (nonatomic, strong) NSString *kind;
@end

@implementation RecoveryApp
- (BOOL)german { return self.language.indexOfSelectedItem == 0; }
- (NSString *)word:(NSString *)de english:(NSString *)en { return self.german ? de : en; }
- (void)refresh {
    NSDictionary *de = @{@"ready": @"Dein Mac ist bereit für die Startfreigabe.", @"check": @"Wir prüfen die Recovery-Umgebung.", @"repair": @"Die passende Recovery-Umgebung wird benötigt.", @"auth": @"Erlaube deinem neuen System zu starten.", @"finish": @"Die Startfreigabe wird abgeschlossen.", @"complete": @"WinDoesNotMac kann jetzt starten."};
    NSDictionary *en = @{@"ready": @"Your Mac is ready for boot authorization.", @"check": @"Checking the Recovery environment.", @"repair": @"The matching Recovery environment is needed.", @"auth": @"Allow your new system to start.", @"finish": @"Finishing boot authorization.", @"complete": @"WinDoesNotMac is ready to start."};
    self.heading.stringValue = (self.german ? de : en)[self.phase] ?: @"WinDoesNotMac";
    NSDictionary *bodyDE = @{@"ready": @"Wir führen den Asahi-Abschlussschritt aus. Halte die macOS-Administratordaten bereit. Ein Neustart erfolgt erst nach deiner Bestätigung.", @"check": @"Die Prüfung stellt fest, ob diese Recovery-Umgebung zur neuen Installation gehört und der Einschaltknopf beim Start durchgehend gedrückt wurde.", @"repair": @"Folge den Hinweisen unten. Nach dem Ausschalten 25 Sekunden warten. Den Einschaltknopf dann in einem Zug gedrückt halten und das neue Installationsvolume auswählen.", @"auth": @"Apple kann deine macOS-Anmeldedaten zweimal anfordern. Die Änderung betrifft die neue Linux-Installation; die Sicherheitsrichtlinie deiner bestehenden macOS-Installation bleibt erhalten.", @"finish": @"Bitte lass den Mac eingeschaltet und das Netzteil angeschlossen. Wir warten auf den tatsächlichen Abschluss der Systembefehle.", @"complete": @"Bestätige den Neustart unten. Danach startet Linux. Die geplante Calamares-Ersteinrichtung folgt dort."};
    NSDictionary *bodyEN = @{@"ready": @"We will run the Asahi completion step. Have your macOS administrator credentials ready. Restart requires your confirmation.", @"check": @"Checking that Recovery belongs to the new installation and that the power button was held continuously during startup.", @"repair": @"Follow the details below. After shutdown wait 25 seconds, hold the power button in one continuous press, then select the new installation volume.", @"auth": @"Apple may request your macOS credentials twice. This affects the new Linux installation; your existing macOS security policy is unchanged.", @"finish": @"Keep your Mac powered on and connected to power. We are waiting for the actual system commands to finish.", @"complete": @"Confirm restart below. Linux will start next. Our planned Calamares first-boot setup runs there."};
    self.body.stringValue = (self.german ? bodyDE : bodyEN)[self.phase] ?: @"";
    self.button.title = [self.phase isEqual:@"ready"] ? [self word:@"Startfreigabe beginnen" english:@"Begin boot authorization"] : [self.phase isEqual:@"complete"] ? [self word:@"Neustart bestätigen" english:@"Confirm restart"] : [self word:@"Weiter" english:@"Continue"];
    if (previewMode) self.body.stringValue = [@"TESTMODUS / TEST MODE — Keine Systemänderungen / No system changes.\n\n" stringByAppendingString:self.body.stringValue];
}
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
    self.phase = @"ready"; self.kind = @"continue"; self.buffer = [NSMutableData data];
    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,900,700) styleMask:NSWindowStyleMaskTitled|NSWindowStyleMaskClosable|NSWindowStyleMaskMiniaturizable backing:NSBackingStoreBuffered defer:NO];
    self.window.delegate = self; self.window.title = @"WinDoesNotMac · Recovery";
    self.window.appearance = [NSAppearance appearanceNamed:NSAppearanceNameDarkAqua];
    NSView *view = self.window.contentView;
    NSTextField *brand = [NSTextField labelWithString:@"WinDoesNotMac"];
    brand.font = [NSFont boldSystemFontOfSize:24]; brand.textColor = [NSColor colorWithRed:1 green:.55 blue:.32 alpha:1]; brand.frame = NSMakeRect(36,632,620,34); [view addSubview:brand];
    self.language = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(720,634,145,30) pullsDown:NO];
    [self.language addItemsWithTitles:@[@"Deutsch", @"English"]]; self.language.target=self; self.language.action=@selector(refresh); [view addSubview:self.language];
    self.heading = [NSTextField wrappingLabelWithString:@""]; self.heading.font=[NSFont boldSystemFontOfSize:28]; self.heading.frame=NSMakeRect(36,532,820,80); [view addSubview:self.heading];
    self.body = [NSTextField wrappingLabelWithString:@""]; self.body.font=[NSFont systemFontOfSize:17]; self.body.frame=NSMakeRect(36,400,820,125); [view addSubview:self.body];
    self.spinner = [[NSProgressIndicator alloc] initWithFrame:NSMakeRect(36,354,28,28)]; self.spinner.style=NSProgressIndicatorStyleSpinning; [view addSubview:self.spinner];
    self.prompt = [NSTextField wrappingLabelWithString:@""]; self.prompt.frame=NSMakeRect(80,335,770,50); [view addSubview:self.prompt];
    self.answer = [[NSTextField alloc] initWithFrame:NSMakeRect(36,289,630,34)]; self.answer.hidden=YES; [view addSubview:self.answer];
    self.password = [[NSSecureTextField alloc] initWithFrame:self.answer.frame]; self.password.hidden=YES; [view addSubview:self.password];
    self.button = [NSButton buttonWithTitle:@"" target:self action:@selector(advance:)]; self.button.frame=NSMakeRect(36,235,350,40); self.button.bezelStyle=NSBezelStyleRounded; self.button.keyEquivalent=@"\r"; [view addSubview:self.button];
    NSScrollView *scroll = [[NSScrollView alloc] initWithFrame:NSMakeRect(36,30,828,185)]; scroll.hasVerticalScroller=YES;
    self.details = [[NSTextView alloc] initWithFrame:scroll.bounds]; self.details.editable=NO; self.details.font=[NSFont monospacedSystemFontOfSize:12 weight:NSFontWeightRegular]; scroll.documentView=self.details; [view addSubview:scroll];
    [self refresh]; [self.window center]; [self.window makeKeyAndOrderFront:nil]; [NSApp activateIgnoringOtherApps:YES];
}
- (BOOL)windowShouldClose:(NSWindow *)sender {
    if (self.task.running) { NSBeep(); return NO; }
    return YES;
}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender { return YES; }
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender { return self.task.running ? NSTerminateCancel : NSTerminateNow; }
- (void)append:(NSString *)line {
    NSRegularExpression *ansi = [NSRegularExpression regularExpressionWithPattern:@"\\x1b\\[[0-?]*[ -/]*[@-~]" options:0 error:NULL];
    line = [ansi stringByReplacingMatchesInString:line options:0 range:NSMakeRange(0,line.length) withTemplate:@""];
    NSString *value = [self.details.string stringByAppendingFormat:@"%@\n", line];
    if (value.length > 16000) value = [value substringFromIndex:value.length - 16000];
    self.details.string = value; [self.details scrollRangeToVisible:NSMakeRange(value.length,0)];
}
- (void)receive:(NSData *)data {
    [self.buffer appendData:data];
    for (;;) {
        NSData *newline = [@"\n" dataUsingEncoding:NSUTF8StringEncoding];
        NSRange range = [self.buffer rangeOfData:newline options:0 range:NSMakeRange(0,self.buffer.length)];
        if (range.location == NSNotFound) break;
        NSData *part = [self.buffer subdataWithRange:NSMakeRange(0,range.location)];
        [self.buffer replaceBytesInRange:NSMakeRange(0,range.location+1) withBytes:NULL length:0];
        NSString *line = [[NSString alloc] initWithData:part encoding:NSUTF8StringEncoding] ?: @"";
        if ([line hasPrefix:@"@@WDN@@"]) {
            NSDictionary *event = [NSJSONSerialization JSONObjectWithData:[[line substringFromIndex:7] dataUsingEncoding:NSUTF8StringEncoding] options:0 error:NULL];
            if ([event[@"type"] isEqual:@"phase"]) { self.phase=event[@"id"]; [self refresh]; }
            if ([event[@"type"] isEqual:@"prompt"]) [self request:@"continue" label:[self word:@"Bitte bestätige, wenn du bereit bist." english:@"Confirm when you are ready."]];
        } else if (line.length) [self append:line];
    }
    NSString *tail = [[NSString alloc] initWithData:self.buffer encoding:NSUTF8StringEncoding];
    NSRegularExpression *prompt = [NSRegularExpression regularExpressionWithPattern:@"(?i)(password|passphrase|username|user name)[^\\r\\n:]*:\\s*$" options:0 error:NULL];
    if (tail && [prompt firstMatchInString:tail options:0 range:NSMakeRange(0,tail.length)]) {
        NSString *kind = ([tail.lowercaseString containsString:@"password"] || [tail.lowercaseString containsString:@"passphrase"]) ? @"password" : @"text";
        [self request:kind label:tail]; [self.buffer setLength:0];
    }
    if (self.buffer.length > 262144) [self.buffer setLength:0];
}
- (void)request:(NSString *)kind label:(NSString *)label {
    self.kind=kind; self.prompt.stringValue=label; self.password.stringValue=@""; self.answer.stringValue=@"";
    self.password.hidden=![kind isEqual:@"password"]; self.answer.hidden=![kind isEqual:@"text"];
    self.button.enabled=YES; [self.spinner stopAnimation:nil];
    if (!self.password.hidden) [self.window makeFirstResponder:self.password];
    else if (!self.answer.hidden) [self.window makeFirstResponder:self.answer];
}
- (void)advance:(id)sender {
    if (previewMode) {
        NSArray *phases=@[@"ready",@"check",@"auth",@"finish",@"complete"];
        NSUInteger index=[phases indexOfObject:self.phase];
        if (index+1<phases.count) self.phase=phases[index+1];
        [self refresh]; self.button.enabled=![self.phase isEqual:@"complete"]; return;
    }
    if (!self.task) {
        NSString *script = [NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:@"step2.sh"];
        self.task = [[NSTask alloc] init]; self.task.executableURL=[NSURL fileURLWithPath:[NSBundle.mainBundle.bundlePath stringByAppendingPathComponent:@"Contents/MacOS/WinDoesNotRecovery"]]; self.task.arguments=@[@"--bridge",script];
        NSPipe *input=[NSPipe pipe], *output=[NSPipe pipe]; self.task.standardInput=input; self.task.standardOutput=output; self.task.standardError=output; self.input=input.fileHandleForWriting;
        __weak RecoveryApp *weakSelf=self;
        output.fileHandleForReading.readabilityHandler=^(NSFileHandle *handle) { NSData *data=handle.availableData; if (!data.length) { handle.readabilityHandler=nil; return; } dispatch_async(dispatch_get_main_queue(), ^{ [weakSelf receive:data]; }); };
        self.task.terminationHandler=^(NSTask *task) { dispatch_async(dispatch_get_main_queue(), ^{ weakSelf.password.stringValue=@""; weakSelf.answer.stringValue=@""; weakSelf.button.enabled=NO; [weakSelf.spinner stopAnimation:nil]; weakSelf.prompt.stringValue= task.terminationStatus==0 ? [weakSelf word:@"Abschlussschritt beendet." english:@"Completion step finished."] : [weakSelf word:@"Der Abschlussschritt wurde mit einem Fehler beendet. Bitte lies die Details." english:@"The completion step failed. Please read the details."]; }); };
        NSError *error=nil;
        if (![self.task launchAndReturnError:&error]) { [self append:error.localizedDescription]; self.task=nil; return; }
        self.language.enabled=NO;
    } else {
        NSString *text=[self.kind isEqual:@"password"]?self.password.stringValue:[self.kind isEqual:@"text"]?self.answer.stringValue:@"";
        if (text.length>2048 || [text rangeOfCharacterFromSet:NSCharacterSet.controlCharacterSet].location!=NSNotFound) { NSBeep(); return; }
        NSData *data=[[text stringByAppendingString:@"\n"] dataUsingEncoding:NSUTF8StringEncoding];
        self.password.stringValue=@""; self.answer.stringValue=@"";
        @try { [self.input writeData:data]; } @catch (NSException *exception) { [self append:@"The installer connection closed."]; }
    }
    self.button.enabled=NO; self.password.hidden=YES; self.answer.hidden=YES; [self.spinner startAnimation:nil];
}
@end

int main(int argc, const char *argv[]) {
    previewMode = argc==2 && !strcmp(argv[1],"--preview");
    if (argc==2 && !strcmp(argv[1],"--probe")) return geteuid()==0 ? 0 : 78;
    if (argc==3 && !strcmp(argv[1],"--bridge")) return Bridge(argv[2]);
    @autoreleasepool {
        if (geteuid()!=0 && !previewMode) return 78;
        NSApplication *app=[NSApplication sharedApplication];
        static RecoveryApp *delegate; delegate=[RecoveryApp new]; app.delegate=delegate; [app run];
    }
    return 0;
}
