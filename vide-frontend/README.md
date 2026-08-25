# 🖥️ Vidio Chatbot Frontend

This repository houses the admin panel, dashboard, and widget demonstration environment for the **Vidio Chatbot** stack. It is built using **Next.js 15 (App Router)**, **React 19**, **Tailwind CSS 4**, and **TypeScript**. 

---

## ✨ Key Features

- 📊 **Overview Stats Dashboard (`/dashboard`)**: Displays high-level analytics tracking total leads, overall meeting count, and total chat conversations.
- 📋 **Leads Control Hub (`/dashboard/leads`)**: An interactive table for sorting leads, featuring order reference numbers, WhatsApp contact fields, and dynamic **🔥 Order Intent** badges. Administrators can edit lead fields directly in-line or trigger email follow-ups.
- 💬 **Conversation Viewer (`/dashboard/chats`)**: Access complete transcripts and message histories recorded between leads and the AI agent.
- 📅 **Meetings Tracker (`/dashboard/meetings`)**: Lists active booked strategy call sessions synchronized with Google Calendar.
- 🔒 **Secure Authorization**: Guarded routes managed via `ProtectedRoute.tsx` with JWT tokens persisted locally in `sessionStorage` (avoiding cookies).
- 🌐 **Widget Demo (`/`)**: Hosts a landing page setup serving the embeddable chatbot widget from `public/widget.js` for testing integration behaviors.

---

## 🛠️ Directory Structure

```text
vide-frontend/
├── app/
│   ├── dashboard/
│   │   ├── page.tsx            ← Overview stats
│   │   ├── chats/page.tsx      ← Chat list + conversation viewer
│   │   ├── leads/page.tsx      ← Leads table + edit modal
│   │   └── meetings/page.tsx   ← Meeting bookings list
│   ├── login/page.tsx          ← Admin login
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx                ← Widget demo page
├── components/
│   ├── ProtectedRoute.tsx      ← JWT auth guard
│   └── Sidebar.tsx             ← Dashboard navigation
├── lib/
│   ├── api.ts                  ← Axios instance + API calls
│   └── apiHelper.ts            ← Admin CRUD helpers + local overrides
├── public/
│   └── widget.js               ← Synced widget copy (cp from widget/widget.js)
├── Dockerfile
├── package.json
└── tsconfig.json
```

---

## ⚙️ Environment Configuration

Create a `.env.local` file in the `vide-frontend` directory with the following variables:

| Variable | Description | Value / Default |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | Public endpoint for client/browser API requests | `http://localhost:8000` |
| `API_URL` | Internal Docker host address for server-side fetches | `http://backend:8000` |

---

## 🚀 Getting Started

### Prerequisites
- **Node.js 20+**
- **npm** or **yarn**

### 1. Run Development Server
1. Navigate to the frontend directory:
   ```bash
   cd vide-frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Boot the local server:
   ```bash
   npm run dev
   ```

Open [http://localhost:3000](http://localhost:3000) in your browser to view the application.

---

## 🐳 Docker Deployment

The application includes a `Dockerfile` for containerization:
```bash
docker build -t vidio-frontend .
docker run -d -p 3000:3000 --env-file .env.local vidio-frontend
```
Or start all services via the root level Docker Compose:
```bash
docker-compose up --build
```
