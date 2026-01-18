# Application Icon

## Creating a Custom Icon for macOS

To add a custom icon to the Structured Products Analysis application:

### Option 1: Quick Method (Using Existing Image)

1. Find or create an icon image (PNG, JPEG, etc.)
2. Open the image in Preview
3. Select All (Cmd+A) and Copy (Cmd+C)
4. In Finder, right-click on `Structured Products.app`
5. Select "Get Info"
6. Click on the small icon in the top-left corner
7. Paste (Cmd+V)

### Option 2: Professional Method (Create .icns file)

1. Create a 1024x1024 PNG image named `icon.png`
2. Create an iconset directory:
   ```bash
   mkdir icon.iconset
   ```

3. Generate all required sizes:
   ```bash
   sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
   sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
   sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
   sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
   sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
   sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
   sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
   sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png
   sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
   sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png
   ```

4. Convert to .icns:
   ```bash
   iconutil -c icns icon.iconset
   ```

5. Copy to application bundle:
   ```bash
   cp icon.icns "../Structured Products.app/Contents/Resources/AppIcon.icns"
   ```

6. Refresh Finder:
   ```bash
   touch "../Structured Products.app"
   killall Finder
   ```

## Icon Design Suggestions

For a financial/structured products application, consider:
- 📊 Chart/graph icon
- 📈 Trending upward arrow
- 💼 Briefcase
- 🏦 Building/institution
- 📋 Document with data
- 🎯 Target/goal

Use professional design tools like:
- Figma
- Sketch
- Adobe Illustrator
- Canva
- SF Symbols (macOS built-in)

## Current Icon

Currently using the default application icon. Follow the steps above to customize.
