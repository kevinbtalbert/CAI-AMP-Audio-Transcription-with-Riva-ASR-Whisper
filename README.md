# Healthcare Call Analytics Platform

**Powered by Cloudera Data Platform**

A web application for transcribing and analyzing patient-provider healthcare calls using NVIDIA NIM's Riva-ASR-Whisper and Nemotron models. Extract healthcare insights, manage audio files, and index data in Solr for search and analytics.

## Key Features

### Audio Transcription
- NVIDIA Riva-ASR-Whisper speech recognition
- Multiple audio formats: WAV, MP3, M4A, FLAC, OGG, OPUS
- Pure Python audio conversion
- Automatic duration calculation

### AI-Powered Analytics
- Nemotron AI integration for healthcare insights
- Medical conditions, medications, and symptoms extraction
- Follow-up actions, urgency assessment, sentiment analysis
- Call type detection (Clinical, Administrative, General)
- Compliance indicators and documentation quality

### File Management
- Nested folder organization
- Drag-and-drop file upload
- Analysis versioning (v1, v2, etc.)
- File deletion from UI

### Solr Integration & Dashboard
- Push analysis results to Cloudera Solr
- Interactive dashboard with categorical insights
- Search and filter across all indexed calls
- View complete Solr documents

### Performance
- Parallel API calls for faster loading
- Concurrent AI processing
- Automatic Knox token renewal
- Real-time model health monitoring

## Quick Start

### Prerequisites
- Python 3.9+
- Cloudera Data Platform (CDP) with:
  - NVIDIA NIM Riva-ASR-Whisper endpoint
  - NVIDIA Nemotron model endpoint (optional)
  - Cloudera Solr (optional)
- CDP Access Token (JWT)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd CAI-AMP-Audio-Transcription-with-Riva-ASR-Whisper
```

2. **Create virtual environment**
```bash
python -m venv ../CAI-AMP-Audio-Transcription-with-Riva-ASR-Whisper_venv
source ../CAI-AMP-Audio-Transcription-with-Riva-ASR-Whisper_venv/bin/activate  # On Windows: ..\venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the application**
```bash
python app.py
```

5. **Open in browser**
```
http://0.0.0.0:8000
```

6. **First-time setup**
   - Click **Settings** in the header
   - Configure your CDP endpoints and tokens
   - Click **Save Settings**
   - Settings persist in `.env` file

## Configuration

### Required Settings

Configure via the UI (Settings → Transcription tab):

| Setting | Description |
|---------|-------------|
| **Riva ASR Whisper Endpoint** | Your CDP Riva ASR endpoint URL |
| **CDP JWT Path** | Path to JWT file (default: `/tmp/jwt`) |
| **CDP Token** | Alternative to JWT file (paste token directly) |

### Optional: AI Summarization

Configure via UI (Settings → AI Summarization tab):

| Setting | Description |
|---------|-------------|
| **Enable Nemotron** | Toggle AI-enhanced summaries |
| **Nemotron Endpoint** | Your CDP Nemotron model URL |
| **Model ID** | e.g., `nvidia/llama-3.3-nemotron-super-49b-v1` |

> **Note**: Nemotron uses the same CDP authentication as Riva ASR

### Optional: Solr Integration

Configure via UI (Settings → Solr Indexing tab):

| Setting | Description |
|---------|-------------|
| **Enable Solr** | Toggle Solr indexing |
| **Solr Base URL** | Knox gateway Solr URL |
| **Collection Name** | Solr collection (default: `healthcare_calls`) |
| **Solr CDP Token** | Separate token for Solr access |

### Optional: Token Auto-Renewal

Configure via UI (Settings → General tab):

| Setting | Description |
|---------|-------------|
| **Enable Auto-Renewal** | Automatically refresh Knox tokens |
| **Knox Renewal Endpoint** | Knox API v2 endpoint |
| **Hadoop JWT Cookie** | `hadoop-jwt` cookie from browser |

> Tokens auto-renew every 22 hours to prevent expiration

### Environment Variables

All settings can also be configured via `.env`:

```env
# Riva ASR Configuration
CDP_BASE_URL=https://ml-xxxxx.cloudera.site/.../riva-whisper-audio-transcribe/v1
CDP_JWT_PATH=/tmp/jwt
CDP_TOKEN=your_token_here

# Nemotron Configuration (Optional)
NEMOTRON_ENABLED=true
NEMOTRON_BASE_URL=https://ml-xxxxx.cloudera.site/.../nemotron/v1
NEMOTRON_MODEL_ID=nvidia/llama-3.3-nemotron-super-49b-v1

# Solr Configuration (Optional)
SOLR_ENABLED=true
SOLR_BASE_URL=https://<gateway>.cloudera.site/solr/
SOLR_COLLECTION_NAME=healthcare_calls
SOLR_TOKEN=your_solr_token_here

# Token Auto-Renewal (Optional)
TOKEN_RENEWAL_ENABLED=true
KNOX_RENEWAL_ENDPOINT=https://hostname/homepage/knoxtoken/api/v2/token/renew
HADOOP_JWT_COOKIE=your_hadoop_jwt_cookie

# Application Settings
AUDIO_FILES_DIR=audio_files
RESULTS_DIR=results
HOST=0.0.0.0
PORT=8000
DEFAULT_LANGUAGE=en
```

## Usage Guide

### Analyzing Calls

1. **Upload or Browse**: Add audio files via upload or browse existing files
2. **Select File**: Click on a file in the sidebar
3. **Analyze**: Click "Analyze Call" button
4. **View Results**: See transcription and AI-extracted insights
5. **Push to Solr** (optional): Index the analysis for dashboard access

### Using the Dashboard

**Requirements**: Solr must be enabled and configured

1. **Access Dashboard**: Click "Dashboard" button in header
2. **View Statistics**: See total calls, urgency distribution, etc.
3. **Explore Insights**: Click on medications, conditions, symptoms to filter
4. **Search**: Use search bar to find specific terms
5. **Apply Filters**: Filter by urgency, call type, or sentiment
6. **View Details**: Click "View" to see complete Solr document

### Analysis Versioning

- Each re-analysis creates a new version (v1, v2, v3...)
- Navigate between versions using arrows
- Latest version shown by default
- All versions stored in `results/` directory

## Healthcare Use Cases

### 1. Clinical Documentation
- Transcribe patient-provider calls
- Extract key medical information automatically
- Generate structured data for EHR systems

### 2. Quality Assurance
- Verify documentation completeness
- Check compliance indicators
- Monitor call quality metrics
- Track follow-up requirements

### 3. Data Analytics
- Search across all calls via Solr dashboard
- Identify medication usage patterns
- Track condition prevalence
- Monitor sentiment trends

### 4. Training & Compliance
- Review call patterns for best practices
- Ensure regulatory compliance (HIPAA)
- Identify training opportunities

## Extracted Healthcare Metrics

### Basic Metadata
- Call duration (automatically calculated)
- Audio format and sample rate
- Transcription confidence score
- Analysis timestamp

### Healthcare Insights (AI-Powered)
- **Participants**: Provider name/role, patient identification
- **Call Summary**: Brief overview of conversation
- **Call Type**: Clinical, Administrative, or General
- **Medical Conditions**: Diseases/conditions with context
- **Medications**: Drug names, dosages, frequencies, context
- **Symptoms**: Patient-reported symptoms with details
- **Follow-up Actions**: Appointments, tests, prescriptions
- **Urgency Level**: Low/medium/high with reasoning
- **Sentiment Analysis**: Positive/neutral/negative with confidence
- **Key Topics**: Main discussion topics
- **Compliance Indicators**: Documentation quality, consent, privacy

### AI-Enhanced Summary (Nemotron)
- Clinical Summary (structured SOAP-like format)
- Key Takeaways (bullet points)
- Recommended Actions (specific next steps)

## Architecture

```
├── app.py                          # FastAPI application & API endpoints
├── config.py                       # Configuration management
├── services/
│   ├── transcription.py            # Riva-ASR integration
│   ├── summarization.py            # Nemotron AI integration
│   ├── analytics.py                # Healthcare analytics engine
│   ├── file_manager.py             # File system management
│   ├── audio_preprocessor.py       # Audio format conversion
│   ├── health_checker.py           # Model status monitoring
│   ├── config_manager.py           # Settings persistence
│   ├── solr_indexer.py            # Solr integration
│   └── token_manager.py            # Knox token auto-renewal
├── static/
│   ├── index.html                  # Web UI
│   ├── styles.css                  # Styling
│   └── app.js                      # Frontend logic
├── audio_files/                    # Audio file storage
├── results/                        # Analysis results (versioned)
├── requirements.txt                # Python dependencies
└── .env                            # Configuration (auto-generated)
```

## API Endpoints

### Files
- `GET /api/files/browse?path=<path>` - Browse files/folders
- `POST /api/files/upload` - Upload audio file
- `POST /api/files/create-folder` - Create new folder
- `DELETE /api/files/delete` - Delete file or folder

### Analysis
- `POST /api/analyze` - Analyze audio file
- `GET /api/result/{file_path}` - Get latest result
- `GET /api/result/{file_path}/versions` - List all versions
- `GET /api/result/{file_path}/version/{version}` - Get specific version

### Health & Configuration
- `GET /api/health/riva` - Check Riva ASR status
- `GET /api/health/nemotron` - Check Nemotron status
- `GET /api/settings` - Get current settings
- `POST /api/settings` - Update settings

### Solr Integration
- `POST /api/solr/push` - Push analysis to Solr
- `GET /api/solr/query` - Query Solr documents
- `GET /api/solr/stats` - Get collection statistics
- `GET /api/solr/categorical-facets/{category}` - Get medication/condition/symptom counts

## Security Best Practices

### Token Management
- Never commit tokens to Git (`.env` is in `.gitignore`)
- Use separate tokens for Riva/Nemotron vs. Solr
- Enable auto-renewal to prevent expiration
- Store `hadoop-jwt` cookie securely

### HIPAA Compliance
- Encrypt data at rest and in transit
- Use HTTPS in production
- Implement access controls
- Audit all data access
- Follow organizational PHI policies

### Production Deployment
- Use strong authentication (not included in demo)
- Deploy behind CDP's security layer
- Enable audit logging
- Implement data retention policies
- Regular security audits

## User Interface Features

### Modern Design
- Healthcare-themed color scheme
- Responsive layout
- Real-time status indicators
- Loading states and progress feedback

### Accessibility
- Keyboard navigation support
- Screen reader friendly
- High contrast text
- Clear error messages

### Interactive Elements
- Drag-and-drop file upload
- Collapsible transcription section
- Clickable categorical insights
- Modal document viewer
- Copy-to-clipboard functionality

## License

See LICENSE file for details.

## Disclaimer

This application is for demonstration purposes. Ensure compliance with healthcare regulations (HIPAA, GDPR), organizational data policies, and CDP security guidelines. Always validate AI-generated insights with healthcare professionals.
