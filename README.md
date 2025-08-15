# K.A.I.R.O.S. - A Symbiotic AI Desktop Assistant

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)
![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?style=for-the-badge&logo=flutter)
![PySide6](https://img.shields.io/badge/PySide6-6.9-2796EC?style=for-the-badge&logo=qt)
![PyTorch](https://img.shields.io/badge/PyTorch-2.7-EE4C2C?style=for-the-badge&logo=pytorch)
![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)

**K.A.I.R.O.S. (Kinetic Artificial Intelligence for Responsive & Organic Systems)** is a context-aware, multi-modal AI desktop assistant designed to create a symbiotic link between your PC and mobile devices, proactively assisting in workflows and automating tasks.

---

![KAIROS Demo Placeholder](https://user-images.githubusercontent.com/26833433/126934442-53b3386e-578f-4330-975a-c603b54a2de1.png)
_A placeholder for your awesome project demo!_

---

## Core Concept 🧠

K.A.I.R.O.S. is not just another voice assistant. It's an **ambient computing experiment** built on a local-first philosophy. It observes your workflow, understands your context, and anticipates your needs without constantly sending your data to the cloud. By linking your desktop and mobile device, it aims to erase the boundary between your main workstation and your handheld companion.

---

## Key Features ✨

* **🗣️ Multi-Modal Interaction:** Control your desktop using **voice commands**, **hand gestures**, a floating **command bar**, or the **mobile companion app**.

* **🧠 Proactive Intelligence:** K.A.I.R.O.S. watches for repetitive workflows and uses a local LLM to **suggest new automation macros** on the fly. Its "Guardian Mode" detects when you're in a flow state and can be configured to silence distractions.

* **🧬 Adaptive Personality:** Provide feedback like "be more concise" or "that was helpful," and the AI's personality traits (**verbosity, formality, proactivity**) will adjust over time.

* **🔗 Symbiotic PC-Mobile Link:**
    * **Shared Clipboard:** Copy on your PC, paste on your phone, and vice-versa.
    * **File Handoff:** Seamlessly transfer a document you're reading on your PC to your phone, opening it to the exact same page.
    * **Browser Handoff:** Send the webpage you're viewing on your PC directly to your phone's browser.
    * **Notification Mirroring:** See your phone's notifications on your desktop dashboard.

* **🤖 Dynamic Task Execution:** Ask K.A.I.R.O.S. to perform complex tasks. It uses a local LLM (**Phi-3**) to write, review, and execute sandboxed Python scripts to get the job done.

* **LOCAL FIRST & PRIVACY-FOCUSED:** All core AI models (Transcription, NLU, Speaker Verification, LLM) run **100% locally on your machine**. Your data stays with you.

* **🛠️ Customizable & Extensible:**
    * Create custom voice commands and complex macros through the UI.
    * The UI is **generative**, reconfiguring itself based on your current task (e.g., "Coding" vs. "Browsing").
    * A simple plugin system allows for easy expansion of capabilities.

---

## Architecture Overview 🏗️

K.A.I.R.O.S. is built on a decoupled, multi-threaded architecture to ensure the UI remains responsive while handling numerous background tasks.

```mermaid
graph TD
    %% Define styles for different component types for better readability
    classDef core fill:#e9f2fc,stroke:#4a90e2,stroke-width:3px,color:#000
    classDef worker fill:#e6fcf5,stroke:#50e3c2,stroke-width:2px,color:#000
    classDef service fill:#f3f4f6,stroke:#6b7280,stroke-width:2px,color:#000
    classDef mobile fill:#fce4ec,stroke:#880e4f,stroke-width:2px,color:#000
    classDef io fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#000
    classDef data fill:#f1f0ef,stroke:#78716c,stroke-width:2px,color:#000

    %% External Entities
    subgraph External Entities
        User((User<br/>Voice, Gestures,<br/>Text Input)):::io
        GitHub((GitHub<br/>Version Updates)):::io
    end
    
    %% K.A.I.R.O.S. Mobile Companion
    subgraph Mobile ["K.A.I.R.O.S. Mobile Companion (Flutter)"]
        direction LR
        FlutterUI[Flutter UI<br/>Dashboard, File Transfer]:::mobile
        ConnectionService[Connection Service<br/>WebSocket + Reconnection]:::mobile
        NotificationService[Notification Service<br/>Background Listener]:::mobile
    end

    %% K.A.I.R.O.S. Desktop Core
    subgraph Desktop ["K.A.I.R.O.S. Desktop Core (Python/PySide6)"]
        direction TB
        
        %% Perception & I/O Layer
        subgraph Perception ["Perception & I/O Layer"]
            direction LR
            AudioWorker["Audio Worker<br/>VAD, Speaker Verification, Whisper"]:::worker
            VideoWorker["Video Worker<br/>Gestures & Pose Tracking"]:::worker
            InputMonitor["Input Monitor<br/>KPM & Mouse Metrics"]:::worker
            ClipboardWorker["Clipboard Worker<br/>Clipboard Change Detection"]:::worker
            ActivityLogger["Activity Logger<br/>Active Window Tracking"]:::worker
        end
        
        %% Core Logic & Orchestration
        subgraph CoreLogic ["Core Logic (The Brain)"]
            ActionManager{"Action Manager<br/>Central Intent Orchestrator"}:::core
            NluEngine["NLU Engine<br/>Intent Recognition"]:::service
            MainWindow["MainWindow<br/>PySide6 UI Thread"]
        end
        
        %% Proactive Intelligence Layer
        subgraph ProactiveIntel ["Proactive Intelligence Layer"]
            direction LR
            TaskContext["Task Context Worker"]:::worker
            FlowState["Flow State Worker"]:::worker
            SessionAnalyzer["Session Analyzer"]:::worker
            HeuristicsTuner["Heuristics Tuner"]:::worker
        end
        
        %% AI, Data & Communication Services
        subgraph Services ["AI, Data & Communication Services"]
            direction LR
            APIServer[(API Server<br/>FastAPI & WebSocket)]:::service
            DiscoveryWorker["Discovery Worker<br/>UDP Broadcast"]:::worker
            LLMHandler[(LLM Handler<br/>Ollama/Phi-3 Interface)]:::service
            MemoryNexus[("Memory Nexus<br/>ChromaDB Vector Store")]:::data
            SpeakerWorker["Speaker Worker<br/>TTS Synthesis"]:::worker
            DatabaseManager[("SQLite DB<br/>Feedback & Analytics")]:::data
            SettingsManager[("Settings Manager<br/>config.json")]:::data
            UpdateChecker["Update Checker"]:::worker
        end
    end
    
    %% --- Define Connections ---

    %% User Input -> Perception
    User -- "Voice Commands" --> AudioWorker
    User -- "Hand Gestures" --> VideoWorker
    User -- "Keyboard/Mouse Events" --> InputMonitor
    User -- "Text Commands" --> MainWindow

    %% Perception -> Core Logic & Proactive Intelligence
    AudioWorker -- "Transcribed Text" --> NluEngine
    VideoWorker -- "Gesture Intent" --> ActionManager
    VideoWorker -- "Head Pose Stats" --> FlowState
    InputMonitor -- "Activity Metrics" --> FlowState
    ActivityLogger -- "Active Window Log" --> TaskContext
    ActivityLogger -- "Action Sequence" --> SessionAnalyzer
    
    %% Core Logic Interactions
    MainWindow -- "UI Events" --> ActionManager
    NluEngine -- "Intent & Entities Object" --> ActionManager
    ActionManager -- "Executes System Actions" --> User
    ActionManager -- "Speaks to User" --> SpeakerWorker
    ActionManager -- "Generates Dynamic Task" --> LLMHandler
    ActionManager -- "Queries/Stores Memories" --> MemoryNexus
    ActionManager -- "Logs Command/Feedback" --> DatabaseManager
    ActionManager -- "Reads/Writes Settings" --> SettingsManager
    
    %% Proactive Intelligence -> Core Logic
    TaskContext -- "User Task Changed (e.g. 'Coding')" --> ActionManager
    FlowState -- "Flow State Changed (Guardian Mode)" --> ActionManager
    SessionAnalyzer -- "Macro Suggestion" --> ActionManager
    HeuristicsTuner -- "User Alert: 'Recommend Retraining'" --> MainWindow
    
    %% Data & Service Connections
    DatabaseManager -- "NLU Accuracy Stats" --> HeuristicsTuner
    UpdateChecker -- "New Version Available" --> MainWindow
    UpdateChecker -- "Checks for update.txt" --> GitHub
    ClipboardWorker -- "Forwards Clipboard Data" --> APIServer
    
    %% Mobile Communication Flow
    DiscoveryWorker -- "Broadcasts PC IP" --> ConnectionService
    APIServer <-- "WebSocket / API Calls" --> ConnectionService
    ConnectionService -- "Handles UI Logic" --> FlutterUI
    NotificationService -- "Forwards Notifications" --> APIServer
```

---

## 🛠️ Tech Stack

| Category           | Technologies                                                                                        |
| ------------------ | --------------------------------------------------------------------------------------------------- |
| **Backend** | Python, PySide6 (Qt), FastAPI, Uvicorn, Playwright                                                  |
| **AI / ML** | PyTorch, Sentence Transformers, OpenAI Whisper, SpeechBrain, Spacy, MediaPipe, Ollama (Phi-3)        |
| **Mobile Frontend**| Flutter, Dart, Provider, WebSocketChannel                                                           |
| **Databases & Tools**| SQLite, ChromaDB (Vector DB), Git, VS Code, PyInstaller                                             |

---

## Getting Started 🚀

Follow these steps to get K.A.I.R.O.S. running on your local machine.

### Prerequisites

* Python 3.11+
* Flutter SDK
* An NVIDIA GPU is **highly recommended** for better performance, but not strictly required.
* [Ollama](https://ollama.com/) installed and running for dynamic task execution.

### Installation

1.  **Clone the repository:**
    ```sh
    git clone <your-repo-url>
    cd kairos_project
    ```

2.  **Set up the Python Environment:**
    ```sh
    # Create a virtual environment
    python -m venv venv

    # Activate it
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt
    ```

3.  **Download AI Models:**
    The first time you run the app, the required models (Whisper, SpeechBrain, etc.) will be downloaded automatically. This may take some time.

4.  **Pull the Local LLM:**
    Make sure Ollama is running and pull the Phi-3 model:
    ```sh
    ollama pull phi3
    ```

5.  **Voice Enrollment (CRITICAL STEP):**
    You must enroll your voice before the first launch.
    ```sh
    python enroll_voice.py
    ```
    Follow the on-screen instructions to create your voiceprint.

6.  **Configure Environment Variables:**
    Rename the `.env.example` file to `.env`. If you plan to use Spotify integration in the future, you will need to add your credentials there.

7.  **Set up the Flutter App:**
    ```sh
    # Navigate to the mobile app directory
    cd kairos_mobile_app

    # Get dependencies
    flutter pub get

    # Return to the root directory
    cd ..
    ```

8.  **Launch K.A.I.R.O.S.!**
    ```sh
    python main.py
    ```

---

## 💡 Future Roadmap

-   [ ] **Advanced Spotify Integration:** Full playback control, playlist management, and song recommendations.
-   [ ] **Calendar & Email Plugin:** Add capabilities to read schedules and compose emails.
-   [ ] **Enhanced Memory System:** Enable the AI to form connections between memories and summarize past activities.
-   [ ] **Web-Based Configuration Dashboard:** A more powerful way to manage macros and settings.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.md) file for details.