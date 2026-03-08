# 🎯 QUICK FIX GUIDE - Fixing the @main Error

## The Error You're Seeing

```
'main' attribute can only apply to one type in a module
```

**Cause**: Both `breakeriosApp.swift` and `breakervisionOSApp.swift` are being compiled in the same target, and both have `@main`.

---

## ✅ SOLUTION 1: Fix Target Membership (Easiest)

### Step 1: Fix iOS App File

1. In Xcode, select **`breakeriosApp.swift`**
2. Open **File Inspector** (View → Inspectors → File Inspector, or press ⌥⌘1)
3. Look for the **"Target Membership"** section
4. **UNCHECK** any visionOS target
5. **KEEP CHECKED** only your iOS target (likely "breakerios")

### Step 2: Create visionOS Target (if not done yet)

1. Go to **File → New → Target**
2. Select **visionOS → App**
3. Name it: `breaker visionOS` or similar
4. Click **Finish**

### Step 3: Add visionOS App File

1. Create the visionOS app file by adding the file I provided: `breakervisionOSApp.swift`
2. When adding it, **ONLY check the visionOS target**
3. **DO NOT check the iOS target**

### Step 4: Set Up All Other Files

**iOS-Only Files** (check iOS target only):
- ✅ `breakeriosApp.swift`
- ✅ `ContentView.swift`
- ✅ `DeviceView.swift`
- ✅ `PairingView.swift`

**visionOS-Only Files** (check visionOS target only):
- ✅ `breakervisionOSApp.swift`
- ✅ `ContentViewVision.swift`
- ✅ `DeviceViewVision.swift`
- ✅ `DeviceVisualizationImmersiveView.swift`
- ✅ `PairingViewVision.swift`
- ✅ `View+GlassEffect.swift`

**Shared Files** (check BOTH targets):
- ✅ `Models.swift`
- ✅ `DeviceViewModel.swift` (and all ViewModels)
- ✅ `APIClient.swift`
- ✅ `WebSocketManager.swift`
- ✅ `ChatWebSocketManager.swift`
- ✅ `BLEManager.swift`
- ✅ `TTSPlayer.swift`
- ✅ `CalendarView.swift`
- ✅ `InsightsView.swift`
- ✅ `SettingsView.swift`
- ✅ `ChatView.swift`
- ✅ `AboutView.swift`

---

## ✅ SOLUTION 2: Use Universal App File (Cleaner)

### Step 1: Remove Old App Files from Targets

1. Select `breakeriosApp.swift`
   - File Inspector → Target Membership
   - **UNCHECK ALL targets**
   - You can delete this file or keep it for reference

2. Select `breakervisionOSApp.swift` (if it exists)
   - File Inspector → Target Membership
   - **UNCHECK ALL targets**
   - You can delete this file or keep it for reference

### Step 2: Add the Universal App File

1. Add the file I created: **`SmartBreakerApp.swift`**
2. In File Inspector → Target Membership:
   - ✅ Check iOS target
   - ✅ Check visionOS target
3. This single file works for both platforms using `#if os(visionOS)`

### Step 3: Build and Test

1. Select iOS simulator → Build (⌘B)
2. Select visionOS simulator → Build (⌘B)
3. Both should compile without errors!

---

## 📁 Recommended Xcode File Structure

```
SmartBreaker Project
│
├── 📱 iOS/
│   ├── breakeriosApp.swift          (or delete if using universal)
│   ├── ContentView.swift
│   ├── DeviceView.swift
│   └── PairingView.swift
│
├── 🥽 visionOS/
│   ├── breakervisionOSApp.swift     (or delete if using universal)
│   ├── ContentViewVision.swift
│   ├── DeviceViewVision.swift
│   ├── DeviceVisualizationImmersiveView.swift
│   ├── PairingViewVision.swift
│   └── View+GlassEffect.swift
│
├── 🔄 Shared/
│   ├── 📦 Models/
│   │   └── Models.swift
│   │
│   ├── 🎭 ViewModels/
│   │   └── DeviceViewModel.swift
│   │
│   ├── 🌐 Networking/
│   │   ├── APIClient.swift
│   │   ├── WebSocketManager.swift
│   │   └── ChatWebSocketManager.swift
│   │
│   ├── 📡 Bluetooth/
│   │   └── BLEManager.swift
│   │
│   ├── 🔊 Audio/
│   │   └── TTSPlayer.swift
│   │
│   └── 📺 Views/
│       ├── CalendarView.swift
│       ├── InsightsView.swift
│       ├── SettingsView.swift
│       ├── ChatView.swift
│       └── AboutView.swift
│
└── 🌍 Universal/ (if using Solution 2)
    └── SmartBreakerApp.swift
```

---

## 🔍 How to Check Target Membership in Xcode

1. **Select any file** in the Project Navigator
2. Open **File Inspector** (⌥⌘1 or View → Inspectors → File Inspector)
3. Scroll down to **"Target Membership"**
4. You'll see checkboxes for each target:
   ```
   Target Membership
   ☐ breakerios
   ☐ breaker visionOS
   ☐ breakeriosTests
   ☐ breakeriosUITests
   ```
5. Check/uncheck as needed

---

## ⚠️ Common Mistakes

### Mistake 1: Both app files in both targets
❌ **Wrong**:
- breakeriosApp.swift → ✅ iOS, ✅ visionOS
- breakervisionOSApp.swift → ✅ iOS, ✅ visionOS

✅ **Correct**:
- breakeriosApp.swift → ✅ iOS, ❌ visionOS
- breakervisionOSApp.swift → ❌ iOS, ✅ visionOS

### Mistake 2: Forgetting to add shared files to both targets
❌ **Wrong**:
- Models.swift → ✅ iOS, ❌ visionOS

✅ **Correct**:
- Models.swift → ✅ iOS, ✅ visionOS

### Mistake 3: Adding platform-specific views to both targets
❌ **Wrong**:
- DeviceViewVision.swift → ✅ iOS, ✅ visionOS

✅ **Correct**:
- DeviceViewVision.swift → ❌ iOS, ✅ visionOS

---

## 🧪 Testing Your Setup

### Test iOS Build
1. Select any **iOS Simulator** (e.g., iPhone 15 Pro)
2. Press **⌘B** to build
3. Should succeed with no errors
4. Press **⌘R** to run
5. Should show iOS UI (TabView at bottom)

### Test visionOS Build
1. Select **Apple Vision Pro** simulator
2. Press **⌘B** to build
3. Should succeed with no errors
4. Press **⌘R** to run
5. Should show visionOS UI (Sidebar navigation)
6. Click **"3D View"** button to test ImmersiveSpace

---

## 🎯 Which Solution Should You Use?

### Use Solution 1 (Separate App Files) if:
- ✅ You want clear separation
- ✅ You're new to multi-platform development
- ✅ You might have different app logic per platform in the future

### Use Solution 2 (Universal App File) if:
- ✅ You want cleaner project structure
- ✅ You're comfortable with `#if os(visionOS)` conditionals
- ✅ The app logic is very similar between platforms

**My Recommendation**: Start with **Solution 1** for clarity, migrate to **Solution 2** later if desired.

---

## 📞 Still Having Issues?

### Error: "Cannot find ContentViewVision in scope"
**Fix**: Make sure `ContentViewVision.swift` is added to the visionOS target

### Error: "Cannot find type 'ImmersiveSpace'"
**Fix**: ImmersiveSpace only works on visionOS. Use `#if os(visionOS)` around it.

### Error: Build succeeds but app crashes on launch
**Fix**: Check that all required files are included in the target:
1. Select target in Project Navigator
2. Go to **Build Phases** tab
3. Expand **"Compile Sources"**
4. Verify all needed .swift files are listed

### Error: "Module compiled with Swift X cannot be imported by Swift Y"
**Fix**: Both targets need the same Swift version:
1. Select **Project** (not target)
2. Go to **Build Settings**
3. Search for "Swift Language Version"
4. Set the same version for all targets

---

## 🎬 Quick Video Guide (Manual Steps)

```
1. [Open Xcode Project]
2. [Select breakeriosApp.swift]
3. [Press ⌥⌘1 to open File Inspector]
4. [Scroll to Target Membership]
5. [Uncheck visionOS target]
6. [Done! ✅]

Repeat for other files as needed.
```

---

## 📚 Next Steps After Fixing

1. ✅ Fix target membership
2. ✅ Build both targets successfully
3. ✅ Test on iOS simulator
4. ✅ Test on visionOS simulator
5. ✅ Test 3D immersive view on visionOS
6. 🚀 Deploy to TestFlight
7. 🎉 Ship to App Store!

---

**Need Help?** Check:
- `PROJECT_STRUCTURE_FIX.md` - Detailed guide
- `README_visionOS.md` - Full visionOS documentation
- `ARCHITECTURE_DIAGRAM.md` - Visual reference

Good luck! 🚀
