# NurseTalk WhatsApp Assistant

## Overview

**NurseTalk** is an AI-powered WhatsApp assistant designed to help parents and caregivers describe symptoms, receive a diagnosis, and get first aid advice for children. The system uses natural language processing and speech synthesis to provide both text and audio responses via WhatsApp, leveraging Twilio's messaging API and a custom AI model.

---

## Features

- **WhatsApp Integration:** Communicate with users via WhatsApp using Twilio's API.
- **AI Diagnosis:** Uses an AI model to analyze described symptoms and generate a diagnosis.
- **First Aid Advice:** Provides step-by-step first aid instructions.
- **Speech Synthesis:** Converts diagnosis and advice into audio messages.
- **Conversation State Management:** Tracks user interactions and symptoms using a state machine.
- **Database Logging:** Stores conversation history for each user.
- **Audio File Management:** Serves audio files via HTTP and cleans up old files automatically.
- **Health Check Endpoint:** Simple endpoint for service monitoring.

---

## Directory Structure

```
MasterProject/
│
├── src/
│   └── Backend/
│       ├── FlaskAPI/
│       │   └── flasky.py         # Main Flask application
│       ├── Model/                # AI model and conversation logic
│       ├── database/             # Database utilities
│       └── ...
├── static/
│   ├── audio/                    # Generated audio files
│   └── temp/                     # Temporary files
├── .env                          # Environment variables (Twilio credentials, etc.)
├── README.md                     # This file
└── LICENSE                       # MIT License
```

---

## How It Works

1. **User Interaction:**  
   Users send messages (text or audio) to the WhatsApp bot.

2. **Webhook Handling:**  
   Incoming messages are received at `/webhook` and processed by a Flask app.

3. **Symptom Collection:**  
   The system collects symptoms using a state machine. When the user indicates they're done, it generates a diagnosis.

4. **AI Model:**  
   The AI model (see `Backend/Model/`) analyzes symptoms and returns a diagnosis and first aid steps.

5. **Response Generation:**  
   The response is cleaned and formatted. Text is sent via WhatsApp, and audio is generated using TTS.

6. **Audio Delivery:**  
   Audio files are served via `/audio/<filename>` and sent as WhatsApp media messages.

7. **Conversation Logging:**  
   All interactions are saved in a SQLite database.

---

## Setup & Installation

### Prerequisites

- Python 3.8+
- [ngrok](https://ngrok.com/) (for local development)
- Twilio account (with WhatsApp Sandbox enabled)
- WhatsApp (for testing)

### Installation

1. **Clone the repository:**
   ```
   git clone https://github.com/yourusername/NurseTalk.git
   cd NurseTalk
   ```

2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Create a `.env` file in the root directory:
   ```
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   ```

4. **Run ngrok:**
   ```
   ngrok http 5000
   ```
   Copy the HTTPS URL provided by ngrok.

5. **Configure Twilio Sandbox:**
   - In Twilio Console, set the "WHEN A MESSAGE COMES IN" webhook to `https://<ngrok-url>/webhook`.
   - Join the sandbox from your WhatsApp by sending the join code to the sandbox number.

6. **Start the Flask app:**
   ```
   python src/Backend/FlaskAPI/flasky.py
   ```

---

## API Endpoints

- `POST /webhook`  
  Main endpoint for incoming WhatsApp messages.

- `GET /audio/<filename>`  
  Serves generated audio files.

- `OPTIONS /audio/<filename>`  
  Handles CORS preflight requests.

- `GET /health`  
  Health check endpoint.

- `GET /conversations/<phone_number>`  
  Retrieves conversation history for a given phone number.

---

## Usage

- **Send a WhatsApp message** to the Twilio sandbox number.
- **Describe symptoms** in text or audio.
- **Receive diagnosis and first aid advice** in both text and audio formats.

---

## License

This project is licensed under the [MIT License](LICENSE):

```
MIT License

Copyright (c) 2025 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

---

## Contact

For questions or support,