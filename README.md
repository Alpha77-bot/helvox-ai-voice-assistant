# E-Commerce Voice Assistant

An intelligent, multilingual voice assistant for customer support and order management in e-commerce platforms through natural voice conversations. The agent uses Google's Gemini Realtime API with LiveKit for real-time voice-to-voice interactions and Weaviate for knowledge base retrieval (RAG).


## 🌟 Overview

The E-Commerce Voice Assistant automates customer support and helps customers with their shopping experience. It conducts natural, conversational interactions to:
- Collect customer information (name, location, preferences)
- Help with product inquiries and recommendations
- Answer questions using an intelligent knowledge base
- Handle order tracking and returns
- Schedule callbacks when needed
- Save customer data for follow-up

## 📋 Prerequisites

Before you begin, ensure you have:

- **Docker & Docker Compose** (v20.10+ and v2.0+)
- **Google Cloud Account** with:
  - Vertex AI API enabled
  - Service account with Vertex AI User role
  - Application Default Credentials configured
- **LiveKit Cloud Account** (free tier available)
- **Node.js 18+** (for local frontend development)
- **Python 3.11+** (for local backend development)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd onboarding-agent
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=<your-api-key>
LIVEKIT_API_SECRET=<your-api-secret>

# Google Cloud Configuration
USE_GOOGLE_AUTH=true

# Weaviate Configuration
WEAVIATE_HOST=weaviate
WEAVIATE_PORT=8081
WEAVIATE_GRPC_HOST=weaviate
WEAVIATE_GRPC_PORT=50051
WEAVIATE_COLLECTION=textCollection
WEAVIATE_PROVIDER=vertex_ai
```

### 3. Launch with Docker Compose

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

This will start:
- **LiveKit Server**: `http://localhost:7880`
- **Flask Backend**: `http://localhost:5023`
- **Next.js Frontend**: `http://localhost:3000`
- **Weaviate**: `http://localhost:8080`
- **Redis**: `localhost:6379`
- **Voice Agent**: Automatically connects to LiveKit

### 4. Access the Frontend

The frontend is automatically started with Docker Compose and will be available at:

**http://localhost:3000**

For local development without Docker:

```bash
cd frontend
pnpm install
pnpm dev
```

Create a `.env.local` file in `frontend/` with:
```bash
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_URL=wss://your-project.livekit.cloud
```

## 🎯 Usage

### Starting a Voice Session

1. **Via Frontend UI**:
   - Open `http://localhost:3000`
   - Click "Start call" to begin a session
   - Grant microphone permissions
   - The agent will greet you and start the conversation

2. **Via Custom Integration**:
```javascript
// Get a LiveKit token
const response = await fetch('http://localhost:5023/getToken?name=UserName');
const token = await response.text();

// Connect to LiveKit room
// Use LiveKit client SDK to establish connection
```

### Agent Conversation Flow

1. **Greeting** (in English):
   - "Good morning/afternoon! Welcome to our e-commerce support..."

2. **Language Detection**:
   - Agent detects user's language from their response
   - Switches to user's preferred language

3. **Information Collection**:
   - Name and location
   - Order inquiry or product interest
   - Customer preferences and requirements

4. **Question Handling**:
   - Agent uses RAG to answer questions from knowledge base
   - Handles concerns naturally

5. **Callback Scheduling** (if needed):
   - If user doesn't have time, schedules callback

6. **Call Summary**:
   - Agent verifies all information is collected
   - Provides next steps
   - Saves customer data automatically

### Accessing Customer Data

Customer interaction data is saved in JSON format to the `docs/leads_data/` directory:

```bash
# View collected customer data
ls docs/leads_data/

# Example: customer_20250116_143022_a7f3b8c1.json
cat docs/leads_data/customer_20250116_143022_a7f3b8c1.json
```

Sample customer data:
```json
{
  "call_id": "customer_20250116_143022_a7f3b8c1",
  "call_start_time": "2025-01-16T14:30:22.000Z",
  "call_end_time": "2025-01-16T14:35:45.000Z",
  "customer_name": "Rajesh Kumar",
  "location": "Bangalore",
  "inquiry_type": "product_inquiry",
  "product_category": "electronics",
  "order_number": null,
  "issue_resolved": true,
  "callback_time": null,
  "satisfaction_rating": "positive"
}
```

## 💾 Backup and Restore

### Creating a Backup

To backup your Weaviate knowledge base:

```bash
# Navigate to project directory
cd /Users/VR/jigyasa/onboarding-agent

# Create a timestamped backup
BACKUP_ID="textcollection-backup-$(date +%Y%m%d-%H%M%S)"
python backend/weaviate_client/weaviate_backup.py backup --id $BACKUP_ID --include textCollection

# Backup will be saved to: backups/$BACKUP_ID/
```

### Exporting Backup (for transfer/archiving)

```bash
# Compress the backup
cd backups
zip -r ~/Downloads/${BACKUP_ID}.zip ${BACKUP_ID}/

# The zip file can now be transferred or archived
```

### Restoring from Backup

```bash
# If backup was exported, first unzip it
cd ~/Downloads
unzip onboarding-backup-20251023-*.zip

# Move backup to backups directory
cd /Users/VR/jigyasa/onboarding-agent
mv ~/Downloads/onboarding-backup-20251023-* backups/

# Restore the backup (replace with your actual backup ID)
python backend/weaviate_client/weaviate_backup.py restore --id textcollection-backup-20251118-134846
```

### Listing Collections

```bash
# View all available collections in Weaviate
python backend/weaviate_client/weaviate_backup.py list-collections
```

### Backup Best Practices

1. **Regular Backups**: Create backups before major knowledge base updates
2. **Naming Convention**: Use timestamped backup IDs for easy tracking
3. **Storage**: Keep compressed backups in a secure location
4. **Testing**: Verify backup integrity by testing restore in a development environment
5. **Version Control**: Document which backup corresponds to which application version

## 🧪 Testing

### Manual Testing

```bash
# Test health endpoint
curl http://localhost:5023/health

# Test token generation
curl "http://localhost:5023/getToken?name=TestUser"
```

### Logs and Debugging

```bash
# View agent logs
docker-compose logs -f agent

# View server logs
docker-compose logs -f app

# View all logs
docker-compose logs -f

# Check Weaviate status
docker-compose logs weaviate
```

## 🐛 Troubleshooting

### Common Issues

1. **"Failed to connect to Weaviate"**
   - Ensure Weaviate container is running: `docker-compose ps`
   - Check Google Cloud credentials are mounted correctly
   - Verify `USE_GOOGLE_AUTH=true` in environment

2. **"No audio from agent"**
   - Check microphone permissions in browser
   - Verify LiveKit server is running on port 7880
   - Check agent logs for errors

3. **"RAG search returns no results"**
   - Check Weaviate is properly configured with embeddings
   - Verify collection name matches `WEAVIATE_COLLECTION`

4. **"Token generation fails"**
   - Verify LiveKit credentials in `.env`
   - Ensure Flask server is running on port 5023


## 📊 Monitoring and Metrics

The agent logs comprehensive information:

```
🎬 Call started - Call ID: customer_20250116_143022_a7f3b8c1
✅ Customer name stored: Rajesh Kumar
✅ Customer location stored: Bangalore
✅ Inquiry details stored:
   - Type: Product Inquiry
   - Category: Electronics
🔍 Tool-based RAG search for: 'order tracking information'
✅ Tool returned 1 high-quality results
💾 Customer data saved successfully to: /app/docs/leads_data/customer_20250116_143022_a7f3b8c1.json
```

## 🙏 Acknowledgments

- [LiveKit](https://livekit.io/) for the real-time voice infrastructure
- [Google Cloud](https://cloud.google.com/) for Vertex AI and Gemini models
- [Weaviate](https://weaviate.io/) for vector database capabilities

**Made with ❤️ for E-Commerce Customers**


