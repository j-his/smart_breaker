# 🚨 IMMEDIATE FIX - @main Error Solution

## The Problem
```
Error: 'main' attribute can only apply to one type in a module
```

Both `breakeriosApp.swift` and `breakervisionOSApp.swift` are in the same target.

---

## ⚡ 5-Minute Fix

### Option 1: Fix Target Membership (Recommended)

**Do this in Xcode:**

1. **Select `breakeriosApp.swift`** in Project Navigator
2. Press **⌥⌘1** (Option+Command+1) to open File Inspector
3. Scroll to **"Target Membership"**
4. **UNCHECK** visionOS target, **KEEP** iOS target checked
5. **Select `breakervisionOSApp.swift`** 
6. **UNCHECK** iOS target, **KEEP** visionOS target checked
7. **Build** (⌘B) - Error should be gone! ✅

### Option 2: Use Universal App (Alternative)

1. **Remove** both `breakeriosApp.swift` and `breakervisionOSApp.swift` from ALL targets
2. **Add** the new `SmartBreakerApp.swift` file I created to BOTH targets
3. **Build** (⌘B) - Works on both platforms! ✅

---

## 📋 Complete Target Membership Guide

### iOS Target ONLY ⚠️
```
✅ breakeriosApp.swift
✅ ContentView.swift
✅ DeviceView.swift
✅ PairingView.swift
```

### visionOS Target ONLY ⚠️
```
✅ breakervisionOSApp.swift
✅ ContentViewVision.swift
✅ DeviceViewVision.swift
✅ DeviceVisualizationImmersiveView.swift
✅ PairingViewVision.swift
✅ View+GlassEffect.swift
```

### BOTH Targets ✅
```
✅ Models.swift
✅ All ViewModels
✅ APIClient.swift
✅ WebSocketManager.swift
✅ ChatWebSocketManager.swift
✅ BLEManager.swift
✅ TTSPlayer.swift
✅ CalendarView.swift
✅ InsightsView.swift
✅ SettingsView.swift
✅ ChatView.swift
✅ AboutView.swift
✅ All other shared code
```

---

## 📚 Documentation I Created

### Quick Reference
1. **QUICK_FIX_GUIDE.md** ← Start here! Step-by-step fix
2. **TARGET_MEMBERSHIP_CHECKLIST.md** ← Printable checklist
3. **VISUAL_STRUCTURE_GUIDE.md** ← Visual diagrams

### Detailed Guides
4. **README_visionOS.md** ← Full feature documentation
5. **PROJECT_STRUCTURE_FIX.md** ← Detailed structure explanation
6. **VISIONOS_QUICKSTART.md** ← Quick start guide
7. **ARCHITECTURE_DIAGRAM.md** ← Architecture diagrams
8. **VisionOS_Migration_Notes.swift** ← Code migration notes

### Files I Created
9. **SmartBreakerApp.swift** ← Universal app file (optional)
10. **breakervisionOSApp.swift** ← visionOS app entry point
11. **ContentViewVision.swift** ← visionOS main view
12. **DeviceViewVision.swift** ← visionOS device view
13. **DeviceVisualizationImmersiveView.swift** ← 3D RealityKit view
14. **PairingViewVision.swift** ← visionOS pairing
15. **View+GlassEffect.swift** ← Glass effect helper

---

## ✅ Verification

After fixing, both should work:

```bash
# iOS Build
1. Select "iPhone 15 Pro" simulator
2. Press ⌘B
3. Should build successfully ✅
4. Press ⌘R to run
5. Should show TabView at bottom

# visionOS Build
1. Select "Apple Vision Pro" simulator
2. Press ⌘B
3. Should build successfully ✅
4. Press ⌘R to run
5. Should show Sidebar navigation
6. Click "3D View" to test immersive space
```

---

## 🆘 Still Stuck?

### Common Issues

**"Cannot find ContentViewVision"**
→ Add ContentViewVision.swift to visionOS target

**"Cannot find type ImmersiveSpace"**
→ Only works on visionOS; check file is visionOS-only

**Build succeeds but crashes**
→ Check all dependencies are in target's Build Phases

**Swift version mismatch**
→ Set same Swift version for all targets in Build Settings

---

## 🎯 Best Practices Going Forward

### When adding NEW files:

**Platform-specific file?**
1. Add file to Xcode
2. Check ONLY the relevant target (iOS OR visionOS)

**Shared file?**
1. Add file to Xcode
2. Check BOTH targets (iOS AND visionOS)

### Golden Rule:
```
ONE @main per target!
✅ iOS target → breakeriosApp.swift (@main)
✅ visionOS target → breakervisionOSApp.swift (@main)
❌ Both in same target → ERROR
```

---

## 📞 Help Resources

- **QUICK_FIX_GUIDE.md** - Most comprehensive fix guide
- **TARGET_MEMBERSHIP_CHECKLIST.md** - File-by-file checklist
- **VISUAL_STRUCTURE_GUIDE.md** - Diagrams and visuals
- Apple Docs: [Creating a multiplatform app](https://developer.apple.com/documentation/xcode/creating-a-multiplatform-app)

---

**You got this! Fix target membership and you're done.** 🚀

The visionOS app is already built and ready - you just need to configure the targets correctly! 🎉
