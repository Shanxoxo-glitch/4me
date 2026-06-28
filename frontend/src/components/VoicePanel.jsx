import { useState, useRef } from 'react'
import { Mic, Loader2, Volume2 } from 'lucide-react'

export default function VoicePanel() {
  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [audioUrl, setAudioUrl] = useState(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaRecorderRef.current = new MediaRecorder(stream)
      chunksRef.current = []

      mediaRecorderRef.current.ondataavailable = (e) => {
        chunksRef.current.push(e.data)
      }

      mediaRecorderRef.current.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/wav' })
        const formData = new FormData()
        formData.append('file', blob, 'audio.wav')

        setIsProcessing(true)
        try {
          const response = await fetch('/api/voice/stt', {
            method: 'POST',
            body: formData
          })
          const data = await response.json()
          setTranscript(data.text)
        } catch (error) {
          console.error('STT error:', error)
        } finally {
          setIsProcessing(false)
        }
      }

      mediaRecorderRef.current.start()
      setIsRecording(true)
    } catch (error) {
      console.error('Error accessing microphone:', error)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
    }
  }

  const textToSpeech = async () => {
    if (!transcript) return

    try {
      const response = await fetch('/api/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: transcript })
      })

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      setAudioUrl(url)
    } catch (error) {
      console.error('TTS error:', error)
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <button
          onClick={isRecording ? stopRecording : startRecording}
          className={`w-32 h-32 rounded-full flex items-center justify-center transition-all ${
            isRecording
              ? 'bg-red-600 hover:bg-red-700 animate-pulse'
              : 'bg-purple-600 hover:bg-purple-700'
          }`}
        >
          {isRecording ? (
            <Loader2 className="w-16 h-16 text-white animate-spin" />
          ) : (
            <Mic className="w-16 h-16 text-white" />
          )}
        </button>
        <p className="mt-4 text-slate-300">
          {isRecording ? 'Recording...' : 'Click to start recording'}
        </p>
      </div>

      {isProcessing && (
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-purple-400 mx-auto" />
          <p className="text-slate-300 mt-2">Processing audio...</p>
        </div>
      )}

      {transcript && (
        <div className="bg-slate-700 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-2">Transcript</h3>
          <p className="text-slate-200 mb-4">{transcript}</p>
          <button
            onClick={textToSpeech}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg px-4 py-2 transition-colors"
          >
            <Volume2 className="w-5 h-5" />
            Speak
          </button>
        </div>
      )}

      {audioUrl && (
        <div className="bg-slate-700 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-2">Audio Output</h3>
          <audio controls src={audioUrl} className="w-full" />
        </div>
      )}
    </div>
  )
}
