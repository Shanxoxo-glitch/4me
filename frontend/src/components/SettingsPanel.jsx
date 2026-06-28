import { useState } from 'react'
import { Save, RefreshCw } from 'lucide-react'

export default function SettingsPanel() {
  const [settings, setSettings] = useState({
    apiUrl: 'http://localhost:8000',
    model: 'deepseek-ai/DeepSeek-V3',
    temperature: 0.7,
    maxTokens: 2000,
    whisperModel: 'base',
    ttsVoiceId: '',
  })

  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    localStorage.setItem('deepseek-settings', JSON.stringify(settings))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleReset = () => {
    const defaultSettings = {
      apiUrl: 'http://localhost:8000',
      model: 'deepseek-ai/DeepSeek-V3',
      temperature: 0.7,
      maxTokens: 2000,
      whisperModel: 'base',
      ttsVoiceId: '',
    }
    setSettings(defaultSettings)
    localStorage.removeItem('deepseek-settings')
  }

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-white">Settings</h2>
        <div className="flex gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg px-4 py-2 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Reset
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg px-4 py-2 transition-colors"
          >
            <Save className="w-4 h-4" />
            Save
          </button>
        </div>
      </div>

      {saved && (
        <div className="bg-green-600/20 border border-green-600 text-green-400 rounded-lg px-4 py-2">
          Settings saved successfully!
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">API URL</label>
          <input
            type="text"
            value={settings.apiUrl}
            onChange={(e) => handleChange('apiUrl', e.target.value)}
            className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Model</label>
          <input
            type="text"
            value={settings.model}
            onChange={(e) => handleChange('model', e.target.value)}
            className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Temperature</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={settings.temperature}
              onChange={(e) => handleChange('temperature', parseFloat(e.target.value))}
              className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Max Tokens</label>
            <input
              type="number"
              min="1"
              value={settings.maxTokens}
              onChange={(e) => handleChange('maxTokens', parseInt(e.target.value))}
              className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Whisper Model</label>
          <select
            value={settings.whisperModel}
            onChange={(e) => handleChange('whisperModel', e.target.value)}
            className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            <option value="tiny">Tiny</option>
            <option value="base">Base</option>
            <option value="small">Small</option>
            <option value="medium">Medium</option>
            <option value="large">Large</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">TTS Voice ID (ElevenLabs)</label>
          <input
            type="text"
            value={settings.ttsVoiceId}
            onChange={(e) => handleChange('ttsVoiceId', e.target.value)}
            placeholder="Optional: Enter ElevenLabs voice ID"
            className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
      </div>

      <div className="bg-slate-700/50 rounded-lg p-4">
        <h3 className="font-semibold text-white mb-2">API Keys</h3>
        <p className="text-slate-300 text-sm mb-2">
          API keys should be configured on the server side in the .env file:
        </p>
        <ul className="text-slate-400 text-sm list-disc list-inside space-y-1">
          <li>ELEVENLABS_API_KEY - For text-to-speech</li>
          <li>OPENAI_API_KEY - For additional features</li>
        </ul>
      </div>
    </div>
  )
}
