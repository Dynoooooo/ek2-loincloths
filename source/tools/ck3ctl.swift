// ck3ctl: send keys to CK3 only (works while CK3 is in the background) and find its window.
//   ck3ctl winid <pid>          print CK3's main window id, for `screencapture -l`
//   ck3ctl key <pid> <code>     press one key by macOS virtual key code (50 = `, 36 = Return)
//   ck3ctl skey <pid> <code>    the same with Shift held (18 = 1: Shift+1 picks an event's first option)
//   ck3ctl type <pid> <text>    type text (US layout)
// Build: swiftc -O -o ck3ctl ck3ctl.swift
import Foundation
import CoreGraphics

let a = CommandLine.arguments
guard a.count >= 3, let pid = pid_t(a[2]) else { print("usage: ck3ctl winid|key|type <pid> [arg]"); exit(2) }

// US layout: character -> (key code, needs shift)
var keys: [Character: (CGKeyCode, Bool)] = [" ": (49, false), "=": (24, false), "-": (27, false), "_": (27, true),
    ".": (47, false), ":": (41, true), ";": (41, false), "{": (33, true), "}": (30, true), "\"": (39, true), "'": (39, false)]
let letters: [Character: CGKeyCode] = ["a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37,
    "j": 38, "k": 40, "n": 45, "m": 46]
for (c, k) in letters { keys[c] = (k, false); keys[Character(c.uppercased())] = (k, true) }
for (c, k) in zip("1234567890", [18, 19, 20, 21, 23, 22, 26, 28, 25, 29] as [CGKeyCode]) { keys[c] = (k, false) }

func press(_ code: CGKeyCode, shift: Bool = false, text: String? = nil) {
    let src = CGEventSource(stateID: .privateState)
    for down in [true, false] {
        guard let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: down) else { continue }
        if shift { e.flags = .maskShift }
        if let t = text {
            var u = Array(t.utf16)
            e.keyboardSetUnicodeString(stringLength: u.count, unicodeString: &u)
        }
        e.postToPid(pid)
        usleep(15000)
    }
}

switch a[1] {
case "winid":
    let list = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] ?? []
    var best = (id: -1, area: 0.0)
    for w in list where (w[kCGWindowOwnerPID as String] as? Int) == Int(pid) && (w[kCGWindowLayer as String] as? Int ?? 1) == 0 {
        if let b = w[kCGWindowBounds as String] as? [String: Any], let wd = b["Width"] as? Double,
           let ht = b["Height"] as? Double, let id = w[kCGWindowNumber as String] as? Int, wd * ht > best.area {
            best = (id, wd * ht)
        }
    }
    print(best.id)
case "key":
    press(CGKeyCode(Int(a[3]) ?? 0))
case "skey":
    press(CGKeyCode(Int(a[3]) ?? 0), shift: true)
case "type":
    for ch in a[3] {
        if let (k, sh) = keys[ch] { press(k, shift: sh, text: String(ch)) } else { print("skipped \(ch)") }
    }
default:
    exit(2)
}
