# FlowGuard Frontend Setup Guide

## Quick Start

1. **Install Dependencies**
   ```bash
   cd frontend/vite-project
   npm install
   ```

2. **Start Development Server**
   ```bash
   npm run dev
   ```

3. **Access the Application**
   - Frontend: http://localhost:5173
   - Backend: http://localhost:8000 (make sure it's running)

## Features

### 🎨 Beautiful UI
- Modern gradient designs
- Smooth animations
- Glass morphism effects
- Responsive layout

### 🔐 Authentication
- **Login Page**: Secure login with email and password
- **Signup Page**: Create account with Gemini API key
- Protected routes for authenticated users

### ⚙️ Settings
- Update Gemini API key anytime
- View account information
- Secure API key management

### 📊 Dashboard
- View all your schemas
- Statistics overview
- Quick actions

### 📤 Upload
- Upload OpenAPI schemas (JSON/YAML)
- Specify API base URL
- Drag and drop file upload

## Backend Endpoints Used

- `POST /auth/signup/` - User registration
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user
- `PUT /auth/update-api-key` - Update Gemini API key
- `GET /api/schemas/my-schemas` - Get user's schemas
- `POST /api/schemas/upload` - Upload schema

## Environment

Make sure your backend is running and CORS is configured for:
- http://localhost:5173
- http://127.0.0.1:5173

## Build for Production

```bash
npm run build
```

The built files will be in the `dist` folder.

