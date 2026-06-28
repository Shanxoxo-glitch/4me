import { useState } from 'react'
import { Play, FileText, Wand2 } from 'lucide-react'
import Editor from '@monaco-editor/react'

export default function CodePanel() {
  const [code, setCode] = useState('// Write your code here\nfunction example() {\n  return "Hello, World!";\n}')
  const [language, setLanguage] = useState('javascript')
  const [instruction, setInstruction] = useState('')
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('edit')

  const handleEdit = async () => {
    if (!instruction.trim()) return

    setIsLoading(true)
    try {
      const response = await fetch('/api/code/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          language,
          instruction
        })
      })

      const data = await response.json()
      setCode(data.edited_code)
      setResult(data)
    } catch (error) {
      console.error('Edit error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleReview = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/code/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, language })
      })

      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error('Review error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleGenerate = async () => {
    if (!instruction.trim()) return

    setIsLoading(true)
    try {
      const response = await fetch('/api/code/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: instruction,
          language,
          context: code
        })
      })

      const data = await response.json()
      setCode(data.code)
      setResult(data)
    } catch (error) {
      console.error('Generate error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setActiveTab('edit')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            activeTab === 'edit' ? 'bg-purple-600 text-white' : 'bg-slate-700 text-slate-300'
          }`}
        >
          <Wand2 className="w-4 h-4" />
          Edit
        </button>
        <button
          onClick={() => setActiveTab('review')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            activeTab === 'review' ? 'bg-purple-600 text-white' : 'bg-slate-700 text-slate-300'
          }`}
        >
          <FileText className="w-4 h-4" />
          Review
        </button>
        <button
          onClick={() => setActiveTab('generate')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            activeTab === 'generate' ? 'bg-purple-600 text-white' : 'bg-slate-700 text-slate-300'
          }`}
        >
          <Play className="w-4 h-4" />
          Generate
        </button>
      </div>

      <div className="flex gap-4">
        <div className="flex-1">
          <div className="mb-2">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="bg-slate-700 text-white rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="javascript">JavaScript</option>
              <option value="python">Python</option>
              <option value="java">Java</option>
              <option value="cpp">C++</option>
              <option value="typescript">TypeScript</option>
              <option value="go">Go</option>
              <option value="rust">Rust</option>
            </select>
          </div>
          <div className="rounded-lg overflow-hidden border border-slate-600">
            <Editor
              height="400px"
              language={language}
              value={code}
              onChange={(value) => setCode(value)}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
              }}
            />
          </div>
        </div>

        <div className="w-80 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              {activeTab === 'edit' ? 'Edit Instruction' : activeTab === 'review' ? 'Review Code' : 'Generate Code'}
            </label>
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder={
                activeTab === 'edit'
                  ? 'Describe the changes you want...'
                  : activeTab === 'review'
                  ? 'Click Review button to analyze code'
                  : 'Describe the code you want to generate...'
              }
              className="w-full h-32 bg-slate-700 text-white rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
              disabled={activeTab === 'review'}
            />
          </div>

          <button
            onClick={activeTab === 'edit' ? handleEdit : activeTab === 'review' ? handleReview : handleGenerate}
            disabled={isLoading || (activeTab !== 'review' && !instruction.trim())}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 text-white rounded-lg px-4 py-3 transition-colors flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Processing...
              </>
            ) : (
              <>
                {activeTab === 'edit' && <Wand2 className="w-5 h-5" />}
                {activeTab === 'review' && <FileText className="w-5 h-5" />}
                {activeTab === 'generate' && <Play className="w-5 h-5" />}
                {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
              </>
            )}
          </button>

          {result && (
            <div className="bg-slate-700 rounded-lg p-4">
              <h4 className="font-semibold text-white mb-2">Result</h4>
              {result.explanation && (
                <p className="text-slate-300 text-sm mb-2">{result.explanation}</p>
              )}
              {result.changes && result.changes.length > 0 && (
                <ul className="text-slate-300 text-sm list-disc list-inside">
                  {result.changes.map((change, idx) => (
                    <li key={idx}>{change}</li>
                  ))}
                </ul>
              )}
              {result.issues && result.issues.length > 0 && (
                <ul className="text-red-400 text-sm list-disc list-inside mt-2">
                  {result.issues.map((issue, idx) => (
                    <li key={idx}>{issue}</li>
                  ))}
                </ul>
              )}
              {result.suggestions && result.suggestions.length > 0 && (
                <ul className="text-green-400 text-sm list-disc list-inside mt-2">
                  {result.suggestions.map((suggestion, idx) => (
                    <li key={idx}>{suggestion}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
