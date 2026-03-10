# AIA-Meetings macOS App

Native macOS menubar application for the AIA-Meetings transcription service.

## Features

- **Menubar app** — lives in your menu bar, always accessible
- **Record meetings** — one-click microphone recording with auto-upload
- **Upload files** — drag & drop or file picker for existing audio files
- **View results** — summary, action items, key decisions, full transcript
- **Copy to clipboard** — formatted markdown summary for pasting

## Requirements

- macOS 14.0 (Sonoma) or later
- Xcode 15+ (for building)
- Running AIA-Meetings backend server

## Build & Run

### Using Swift Package Manager

```bash
cd macos-app/AIA-Meetings
swift build
swift run
```

### Using Xcode

1. Open `macos-app/AIA-Meetings` as a Swift Package in Xcode
2. Select the `AIA-Meetings` scheme
3. Build & Run (Cmd+R)

**Important:** Grant microphone access when prompted.

## Setup

1. Launch the app — it appears in the menu bar
2. Go to **Settings** tab
3. Enter your **Server URL** (e.g., `http://localhost:8000`)
4. Enter your **API Key** (create one via `curl -X POST http://localhost:8000/api/v1/auth/keys?name=mac-app`)
5. Click **Test Connection** to verify

## Usage

### Recording
1. Click the **Record** tab
2. Optionally enter a meeting title
3. Click the mic button to start recording
4. Click stop to finish — the audio is automatically uploaded and processed
5. Results appear in the **Meetings** tab

### Upload existing file
1. Click **Upload audio file** in the Record tab
2. Select an mp3, wav, m4a, or other audio file
3. The file is uploaded and processed automatically

### View results
1. Switch to the **Meetings** tab
2. Click any meeting to see full details
3. Use the copy button to copy the summary as markdown
