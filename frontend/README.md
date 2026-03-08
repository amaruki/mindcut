# YouTube Heatmap Clipper - Frontend SPA Architecture

## Overview

The application's frontend has been refactored from static HTML/JS template files rendered by Jinja2 into a modern **Vite + React Single Page Application (SPA)**.

### Key Technologies

- **React 18:** Component-based UI rendering.
- **Vite:** Blazing fast development server and optimized build tool.
- **React Router DOM (HashRouter):** Client-side routing.
- **Flask:** Backend API server, now serving the static SPA assets.

## Running the Application

A single command orchestrates the entire full-stack app locally in development mode:

```bash
start.bat
```

This script will:

1. Open a terminal to run `npm run dev` in the `frontend/` directory (starts the Vite dev server on port `5173`).
2. Run the `webapp.py` Flask backend on port `5000`.

The applications will automatically proxy requests. In development, open `http://localhost:5173`.
API requests sent to `/api/*` and `/clips/*` by the Vite frontend are routed seamlessly to the Flask backend running on `5000`.

## Building for Production

To build the SPA for production (or Electron):

```bash
cd frontend
npm run build
```

Vite will compile and bundle the React app into the `frontend/dist` directory. Flask is configured in `webapp.py` to serve this `dist` folder as its static root.
Once built, running `python webapp.py` alone will serve the fully functional production application at `http://localhost:5000`.
