# MindCut 🎬🧠

Automatically extract viral-ready clips from YouTube videos using heatmap data (Most Replayed) and AI-driven analysis.

## 🚀 Key Features

- **Heatmap Scanning**: Automatically finds the "Most Replayed" sections of any YouTube video.
- **AI-Powered Scoring**: Uses LLMs to analyze transcripts and rank segments based on viral potential.
- **Auto-Cropping**: Converts horizontal videos to vertical (9:16) formats optimized for TikTok, Reels, and Shorts.
- **Smart Subtitles**: Generates and burns subtitles with customizable fonts and positions.
- **Batch Processing**: Process multiple segments at once.
- **YouTube Integration**: Direct upload support for multiple channels with metadata generation.

## 🛠️ Prerequisites

- **Python**: 3.10 or higher.
- **FFmpeg**: Must be installed and available in your system's PATH.
- **Fonts**: Recommended to have some TTF fonts in a `fonts/` directory for subtitle rendering.

## 📦 Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/yourusername/youtube-heatmap-clipper.git
   cd youtube-heatmap-clipper
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Setup**:
   Copy `.env.example` to `.env` and fill in your details (API keys, etc.):
   ```bash
   cp .env.example .env
   ```

## 🖥️ Usage

You can start the web interface using either the Python script or the provided batch file (Windows).

**Option 1: Python**

```bash
python run.py
```

**Option 2: Batch File**
Double-click `start.bat`.

The application will be available at `http://127.0.0.1:5000`.

## 🛠️ Development Setup

If you want to contribute or customize **MindCut**, follow these steps to set up a full development environment.

### 1. Advanced Dependency Installation

MindCut relies on several external tools and libraries:

- **FFmpeg**: Required for all video processing (cropping, merging, subtitles).
  - **Windows**: `winget install Gyan.FFmpeg`
  - **macOS**: `brew install ffmpeg`
  - **Linux**: `sudo apt install ffmpeg`
- **Faster-Whisper**: The application automatically downloads models (default is `small`) on the first run of a subtitle task. Ensure you have ~500MB+ of disk space.
- **Python Packages**: Re-install or update via `pip install -r requirements.txt`.

### 2. YouTube API & Credentials

To enable YouTube uploading and listing:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the **YouTube Data API v3**.
3. Create **OAuth 2.0 Client IDs** (type: Desktop App).
4. Download the JSON file and rename it to `client_secret.json` in the project root.
5. The first time you upload, a `token.json` will be generated after browser authentication.
6. **MindCut** supports multiple accounts; credentials for linked channels are stored in `accounts.json`.

### 3. Environment Variables (.env)

Customize the AI behavior and application defaults by editing your `.env` file:

| Variable             | Description                                                                 |
| :------------------- | :-------------------------------------------------------------------------- |
| `AI_API_URL`         | Endpoint for your AI provider (e.g., OpenAI, Anthropic, or local LLM).      |
| `AI_MODEL`           | The specific model identifier (e.g., `gpt-4o`, `claude-3-5-sonnet`).        |
| `AI_API_KEY`         | Your secret API key.                                                        |
| `AI_SEGMENT_PROMPT`  | Custom system instructions for scoring video segments.                      |
| `AI_METADATA_PROMPT` | Instructions for generating titles/descriptions.                            |
| `WHISPER_MODEL`      | Default Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`). |

### 4. Running in Debug Mode

For development, you can run the Flask app with hot-reloading:

```bash
# Set environment to development
export FLASK_ENV=development  # Windows: set FLASK_ENV=development
python webapp.py
```

## 📁 Project Structure

- `core/`: Core logic for scraping, clipping, and AI processing.
  - `media/`: FFmpeg wrappers and video manipulation.
  - `analysis/`: AI scoring and metadata generation logic.
- `static/`: Frontend assets (vanilla CSS, JS).
- `templates/`: HTML templates for the Flask web app.
- `clips/`: Generated output clips (grouped by video title).
- `fonts/`: Store `.ttf` fonts here for auto-detection in subtitles.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
