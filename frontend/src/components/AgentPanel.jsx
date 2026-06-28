import { useState } from 'react'
import { Play, List, Loader2 } from 'lucide-react'

export default function AgentPanel() {
  const [task, setTask] = useState('')
  const [context, setContext] = useState('')
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [showTools, setShowTools] = useState(false)

  const tools = [
    { name: 'web_search', description: 'Search the web for information' },
    { name: 'code_interpreter', description: 'Execute Python code' },
    { name: 'file_read', description: 'Read file contents' },
    { name: 'file_write', description: 'Write to files' },
  ]

  const executeAgent = async () => {
    if (!task.trim()) return

    setIsLoading(true)
    setResult(null)

    try {
      const response = await fetch('/api/agent/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task,
          context: context || undefined,
          max_iterations: 10
        })
      })

      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error('Agent error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Task</label>
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Describe the task you want the agent to complete..."
            className="w-full h-24 bg-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Context (optional)</label>
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="Provide additional context for the task..."
            className="w-full h-20 bg-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={executeAgent}
            disabled={isLoading || !task.trim()}
            className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 text-white rounded-lg px-4 py-3 transition-colors flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Executing...
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                Execute Task
              </>
            )}
          </button>

          <button
            onClick={() => setShowTools(!showTools)}
            className="bg-slate-700 hover:bg-slate-600 text-white rounded-lg px-4 py-3 transition-colors flex items-center gap-2"
          >
            <List className="w-5 h-5" />
            Tools
          </button>
        </div>

        {showTools && (
          <div className="bg-slate-700 rounded-lg p-4">
            <h4 className="font-semibold text-white mb-3">Available Tools</h4>
            <ul className="space-y-2">
              {tools.map((tool) => (
                <li key={tool.name} className="text-slate-300">
                  <span className="font-medium text-purple-400">{tool.name}:</span> {tool.description}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {result && (
        <div className="bg-slate-700 rounded-lg p-4 space-y-4">
          <div>
            <h4 className="font-semibold text-white mb-2">Result</h4>
            <p className="text-slate-200 whitespace-pre-wrap">{result.result}</p>
          </div>

          {result.steps && result.steps.length > 0 && (
            <div>
              <h4 className="font-semibold text-white mb-2">Execution Steps</h4>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {result.steps.map((step, idx) => (
                  <div key={idx} className="bg-slate-800 rounded p-3">
                    <div className="text-sm text-purple-400 mb-1">Step {step.iteration} - {step.type}</div>
                    <p className="text-slate-300 text-sm">{step.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.tool_calls && result.tool_calls.length > 0 && (
            <div>
              <h4 className="font-semibold text-white mb-2">Tool Calls</h4>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {result.tool_calls.map((call, idx) => (
                  <div key={idx} className="bg-slate-800 rounded p-3">
                    <div className="text-sm text-purple-400 mb-1">{call.tool}</div>
                    <pre className="text-slate-300 text-xs">{JSON.stringify(call.parameters, null, 2)}</pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
