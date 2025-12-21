import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ClientList from './components/ClientList';
import ClientEditor from './components/ClientEditor';
import ChatInterface from './components/ChatInterface';
import { Toaster } from "@/components/ui/sonner"

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50 text-gray-900 font-sans">
        <nav className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
          <div className="max-w-6xl mx-auto flex items-center gap-4">
            <div className="bg-blue-600 text-white p-2 rounded-lg font-bold">AI</div>
            <div className="flex gap-4">
              <span className="font-semibold text-lg text-gray-700">Agent Orchestrator</span>
              <a href="/chat" className="text-gray-600 hover:text-blue-600 self-center">Chat Demo</a>
            </div>
          </div>
        </nav>
        <Routes>
          <Route path="/" element={<ClientList />} />
          <Route path="/chat" element={<ChatInterface />} />
          <Route path="/client/:id" element={<ClientEditor />} />
          <Route path="/new" element={<ClientEditor />} />
        </Routes>
        <Toaster />
      </div>
    </Router>
  );
}

export default App;
