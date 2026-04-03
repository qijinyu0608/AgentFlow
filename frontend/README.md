# AgentMesh Frontend

Web UI interface for AgentMesh multi-agent system.

## Features

- 🎯 **Chat Interface**: Clean chat window where users can input requirements and tasks
- 📋 **Task List**: Collapsible task panel on the left side, showing real-time status of Agent team operations
- 🔄 **Real-time Status**: Task status updates in real-time (running, completed)
- 📱 **Responsive Design**: Supports both desktop and mobile access
- ✨ **Modern UI**: Beautiful interface based on Vue 3 and modern CSS design

## Tech Stack

- **Vue 3**: Using Composition API
- **Vite**: Fast build tool
- **CSS3**: Modern CSS features including Flexbox, Grid, animations, etc.
- **JavaScript ES6+**: Modern JavaScript syntax

## Quick Start

### Install Dependencies

```bash
npm install
```

### Start Development Server

```bash
npm run dev
```

The project will start at http://localhost:3000.

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── App.vue          # Main application component
│   ├── main.js          # Application entry point
│   └── style.css        # Global styles
├── index.html           # HTML template
├── package.json         # Project configuration
├── vite.config.js       # Vite configuration
└── README.md           # Project documentation
```

## Interface Description

### Main Components

1. **Task Sidebar** (`task-sidebar`)
   - Collapsible/expandable task list
   - Shows task status (running, completed)
   - Displays executing Agent information
   - Shows task creation time

2. **Chat Area** (`chat-container`)
   - Welcome interface and example prompts
   - Message history
   - Auto-scroll to latest messages

3. **Input Area** (`chat-input-container`)
   - Auto-resizing text input
   - Send button and loading status
   - Supports Enter to send, Shift+Enter for new line

### Interactive Features

- Click the top-left button to collapse/expand task list
- Click example prompts to quickly fill input box
- Task status updates in real-time (simulated)
- Supports keyboard shortcuts

## Future Development Plans

- [ ] Integrate backend API endpoints
- [ ] Add WebSocket real-time communication
- [ ] Add task detail pages
- [ ] Add Agent status monitoring
- [ ] Implement task history
- [ ] Add user authentication features

## Development Notes

Current version is a demo version using mock data. For actual deployment, you need to:

1. Connect to AgentMesh backend API
2. Implement WebSocket connection for real-time updates
3. Add error handling and reconnection mechanisms
4. Optimize performance and user experience 