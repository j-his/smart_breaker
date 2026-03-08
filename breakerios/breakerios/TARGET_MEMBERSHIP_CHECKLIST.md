# 📋 TARGET MEMBERSHIP CHECKLIST

Use this checklist to ensure correct target membership for all files.

---

## iOS TARGET ONLY ⚠️

These files should **ONLY** be checked for your iOS target:

```
□ breakeriosApp.swift
□ ContentView.swift
□ DeviceView.swift
□ PairingView.swift
```

---

## visionOS TARGET ONLY ⚠️

These files should **ONLY** be checked for your visionOS target:

```
□ breakervisionOSApp.swift
□ ContentViewVision.swift
□ DeviceViewVision.swift
□ DeviceVisualizationImmersiveView.swift
□ PairingViewVision.swift
□ View+GlassEffect.swift
```

---

## BOTH TARGETS ✅

These files should be checked for **BOTH** iOS and visionOS targets:

### Models
```
□ Models.swift
□ (any other model files)
```

### ViewModels
```
□ DeviceViewModel.swift (inside DeviceView.swift or separate)
□ (any other ViewModel files)
```

### Networking
```
□ APIClient.swift
□ WebSocketManager.swift
□ ChatWebSocketManager.swift
```

### Bluetooth & Hardware
```
□ BLEManager.swift
□ TTSPlayer.swift
```

### Shared Views
```
□ CalendarView.swift
□ InsightsView.swift
□ SettingsView.swift
□ ChatView.swift
□ AboutView.swift
□ (any other shared views)
```

### Utilities & Extensions
```
□ Any utility files
□ Any extension files (except View+GlassEffect.swift)
```

---

## NEITHER TARGET (Documentation)

These files don't need to be in any target:

```
□ README_visionOS.md
□ PROJECT_STRUCTURE_FIX.md
□ QUICK_FIX_GUIDE.md
□ VISIONOS_QUICKSTART.md
□ ARCHITECTURE_DIAGRAM.md
□ TARGET_MEMBERSHIP_CHECKLIST.md
□ VisionOS_Migration_Notes.swift
□ Info-visionOS.plist (set in build settings instead)
```

---

## 🔍 How to Check Each File

For each file in your project:

1. **Click on the file** in Xcode's Project Navigator (left sidebar)
2. **Open File Inspector**: 
   - Menu: View → Inspectors → File Inspector
   - OR Keyboard: ⌥⌘1 (Option+Command+1)
3. **Scroll down** to "Target Membership" section
4. **Check/Uncheck** appropriate targets based on this list
5. **Repeat** for all files

---

## ⚡ Quick Reference

| File Type | iOS Target | visionOS Target |
|-----------|------------|-----------------|
| breakeriosApp.swift | ✅ | ❌ |
| breakervisionOSApp.swift | ❌ | ✅ |
| ContentView.swift | ✅ | ❌ |
| ContentViewVision.swift | ❌ | ✅ |
| DeviceView.swift | ✅ | ❌ |
| DeviceViewVision.swift | ❌ | ✅ |
| Models.swift | ✅ | ✅ |
| APIClient.swift | ✅ | ✅ |
| BLEManager.swift | ✅ | ✅ |
| CalendarView.swift | ✅ | ✅ |

---

## 🎯 After You're Done

Build both targets to verify:

```bash
# Build iOS
⌘B with iOS Simulator selected

# Build visionOS  
⌘B with Apple Vision Pro Simulator selected
```

Both should build successfully without the `@main` error! ✅

---

## 🆘 Emergency Fix

If you're still getting errors, here's the nuclear option:

1. **Create a new visionOS target** (File → New → Target → visionOS)
2. **Don't add ANY files automatically**
3. **Manually add files** one by one using this checklist
4. **Delete the old broken target**
5. **Rename the new target** to match your preferred name

This ensures clean target membership from scratch.

---

**Print this checklist and check off files as you configure them!** ✅
