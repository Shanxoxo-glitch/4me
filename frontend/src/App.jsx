import { useState } from 'react'
import { MessageSquare, Mic, Code, Bot, Settings } from 'lucide-react'
import ChatPanel from './components/ChatPanel'
import VoicePanel from './components/VoicePanel'
import CodePanel from './components/CodePanel'
import AgentPanel from './components/AgentPanel'
import SettingsPanel from './components/SettingsPanel'

function App() {
  const [activeTab, setActiveTab] = useState('chat')

  const tabs = [
    { id: 'chat', icon: MessageSquare, label: 'Chat' },
    { id: 'voice', icon: Mic, label: 'Voice' },
    { id: 'code', icon: Code, label: 'Code' },
    { id: 'agent', icon: Bot, label: 'Agent' },
    { id: 'settings', icon: Settings, label: 'Settings' },
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto p-4">
        <header className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-white mb-2">DeepSeek-V3 AI Assistant</h1>
          <p className="text-purple-300">Voice-enabled, agentic, and code-capable AI</p>
        </header>

        <div className="flex gap-4">
          <nav className="w-64 bg-slate-800/50 backdrop-blur rounded-lg p-4 h-fit">
            <ul className="space-y-2">
              {tabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <li key={tab.id}>
                    <button
                      onClick={() => setActiveTab(tab.id)}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                        activeTab === tab.id
                          ? 'bg-purple-600 text-white'
                          : 'text-slate-300 hover:bg-slate-700/50'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <span>{tab.label}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </nav>

          <main className="flex-1 bg-slate-800/50 backdrop-blur rounded-lg p-6 min-h-[600px]">
            {activeTab === 'chat' && <ChatPanel />}
            {activeTab === 'voice' && <VoicePanel />}
            {activeTab === 'code' && <CodePanel />}
            {activeTab === 'agent' && <AgentPanel />}
            {activeTab === 'settings' && <SettingsPanel />}
          </main>
        </div>
      </div>
    </div>
  )
}

export default App
