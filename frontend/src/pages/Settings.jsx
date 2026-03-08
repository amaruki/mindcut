import React, { useState, useEffect } from 'react';

const SETTING_KEYS = [
  'ratio', 'crop', 'padding', 'max_clips',
  'subtitle', 'whisper_model', 'subtitle_font_select', 'subtitle_font_custom', 'subtitle_location', 'subtitle_fontsdir',
  'hook_enabled', 'hook_voice', 'hook_voice_rate', 'hook_voice_pitch', 'hook_font_size',
  'ai_api_url', 'ai_model', 'ai_api_key', 'ai_prompt', 'ai_metadata_prompt'
];

export default function Settings() {
  const [settings, setSettings] = useState({});
  const [toastVisible, setToastVisible] = useState(false);
  const [testingVoice, setTestingVoice] = useState(false);

  useEffect(() => {
    const loaded = {};
    SETTING_KEYS.forEach(key => {
      const val = localStorage.getItem(`yt_config_${key}`);
      if (val !== null) loaded[key] = val;
    });
    setSettings(prev => ({ ...prev, ...loaded }));
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setSettings(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = () => {
    Object.keys(settings).forEach(key => {
      localStorage.setItem(`yt_config_${key}`, settings[key]);
    });
    setToastVisible(true);
    setTimeout(() => setToastVisible(false), 3000);
  };

  const testVoice = async () => {
    setTestingVoice(true);
    try {
      const res = await fetch('/api/tts/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          voice: settings.hook_voice || 'en-US-GuyNeural', 
          rate: settings.hook_voice_rate || '+15%', 
          pitch: settings.hook_voice_pitch || '+5Hz', 
          text: "Testing the hook voice. How does it sound?" 
        })
      });
      if (!res.ok) throw new Error('Failed to generate preview');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
    } catch (e) {
      alert(e.message);
    } finally {
      setTestingVoice(false);
    }
  };

  return (
    <main className="flex-1 overflow-y-auto flex justify-center py-10 px-6 custom-scrollbar">
      <div className="w-full max-w-[800px] flex flex-col gap-6">
        <div className="mb-2">
          <h1 className="text-2xl font-semibold m-0 text-fg">Application Settings</h1>
          <p className="text-fg-muted mt-1 text-sm">Configure your default preferences for clip generation and AI features.</p>
        </div>

        {/* Output Formatting */}
        <div className="bg-bg-panel/65 border border-border-main rounded-2xl p-6 shadow-md backdrop-blur-md">
          <h2 className="text-base font-semibold m-0 mb-4 text-accent flex items-center gap-2 pb-3 border-b border-border-main">
            Output Formatting
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Ratio Default</label>
              <select name="ratio" value={settings.ratio || '9:16'} onChange={handleChange} className="input">
                <option value="9:16">9:16 (Shorts)</option>
                <option value="1:1">1:1</option>
                <option value="16:9">16:9</option>
                <option value="original">Original</option>
              </select>
            </div>
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Crop Target Default</label>
              <select name="crop" value={settings.crop || 'default'} onChange={handleChange} className="input">
                <option value="default">Default</option>
                <option value="face">Face Track</option>
                <option value="split_left">Split Left</option>
                <option value="split_right">Split Right</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-fg-muted text-xs font-medium">Pad (sec)</label>
              <input name="padding" type="number" min="0" value={settings.padding || '10'} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-fg-muted text-xs font-medium">Max clips limit</label>
              <input name="max_clips" type="number" min="1" value={settings.max_clips || '6'} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" />
            </div>
          </div>
        </div>

        {/* Subtitles & Transcribe */}
        <div className="bg-bg-panel/65 border border-border-main rounded-2xl p-6 shadow-md backdrop-blur-md">
          <h2 className="text-base font-semibold m-0 mb-4 text-accent flex items-center gap-2 pb-3 border-b border-border-main">
            Subtitles & Transcribe
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Enable Burn-in by Default</label>
              <select name="subtitle" value={settings.subtitle || 'n'} onChange={handleChange} className="input">
                <option value="n">No</option>
                <option value="y">Yes</option>
              </select>
            </div>
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Model</label>
              <select name="whisper_model" value={settings.whisper_model || 'small'} onChange={handleChange} className="input">
                <option value="tiny">tiny</option>
                <option value="base">base</option>
                <option value="small">small</option>
                <option value="large-v3">large</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Font Face</label>
              <select name="subtitle_font_select" value={settings.subtitle_font_select || 'Plus Jakarta Sans'} onChange={handleChange} className="input">
                <option value="Plus Jakarta Sans">Plus Jakarta Sans</option>
                <option value="Montserrat">Montserrat</option>
                <option value="custom">Custom...</option>
              </select>
              {settings.subtitle_font_select === 'custom' && (
                <input name="subtitle_font_custom" value={settings.subtitle_font_custom || ''} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25 mt-2" placeholder="Custom font name" />
              )}
            </div>
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Location</label>
              <select name="subtitle_location" value={settings.subtitle_location || 'bottom'} onChange={handleChange} className="input">
                <option value="bottom">Bottom</option>
                <option value="center">Centered</option>
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-fg-muted text-xs font-medium">Fonts Directory</label>
            <input name="subtitle_fontsdir" value={settings.subtitle_fontsdir || 'fonts'} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" placeholder="fonts" />
          </div>
        </div>

        {/* Hook Intro Settings */}
        <div className="bg-bg-panel/65 border border-border-main rounded-2xl p-6 shadow-md backdrop-blur-md">
          <h2 className="text-base font-semibold m-0 mb-4 text-accent flex items-center gap-2 pb-3 border-b border-border-main">
            Hook Intro (New)
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Enable Hook Intro</label>
              <select name="hook_enabled" value={settings.hook_enabled || 'n'} onChange={handleChange} className="input">
                <option value="n">No</option>
                <option value="y">Yes</option>
              </select>
            </div>
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Hook Voice</label>
              <div className="flex gap-2">
                <select name="hook_voice" value={settings.hook_voice || 'en-US-GuyNeural'} onChange={handleChange} className="input" style={{ flex: 1 }}>
                  <option value="en-US-GuyNeural">English - Guy (Male)</option>
                  <option value="en-US-AvaNeural">English - Ava (Female)</option>
                  <option value="en-GB-SoniaNeural">British - Sonia (Female)</option>
                  <option value="id-ID-ArdiNeural">Indonesia - Ardi (Male)</option>
                  <option value="id-ID-GadisNeural">Indonesia - Gadis (Female)</option>
                </select>
                <button className="bg-transparent text-fg border border-border-main rounded-lg py-2.5 px-4 font-semibold text-[13px] hover:bg-white/5 cursor-pointer disabled:opacity-50 h-[38px]" type="button" onClick={testVoice} disabled={testingVoice}>
                  {testingVoice ? '...' : '🔊'}
                </button>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Voice Speed (Rate)</label>
              <input name="hook_voice_rate" value={settings.hook_voice_rate || '+15%'} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" placeholder="+15% or -10%" />
            </div>
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">Voice Pitch</label>
              <input name="hook_voice_pitch" value={settings.hook_voice_pitch || '+5Hz'} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" placeholder="+5Hz or -2st" />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-fg-muted text-xs font-medium">Hook Font Size</label>
            <input name="hook_font_size" type="number" min="20" max="200" value={settings.hook_font_size || '72'} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" />
          </div>
        </div>

        {/* Advanced AI Control */}
        <div className="bg-bg-panel/65 border border-border-main rounded-2xl p-6 shadow-md backdrop-blur-md">
          <h2 className="text-base font-semibold m-0 mb-4 text-accent flex items-center gap-2 pb-3 border-b border-border-main">
            Advanced AI Control
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">API URL</label>
              <input name="ai_api_url" value={settings.ai_api_url || ''} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" placeholder="https://api.openai.com/..." />
            </div>
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-fg-muted text-xs font-medium">AI Model</label>
              <input name="ai_model" value={settings.ai_model || ''} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" placeholder="gpt-4o" />
            </div>
          </div>
          <div className="flex flex-col gap-2 mb-4">
            <label className="text-fg-muted text-xs font-medium">API Key</label>
            <input name="ai_api_key" type="password" value={settings.ai_api_key || ''} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" placeholder="sk-..." />
          </div>
          <div className="flex flex-col gap-2 mt-3 mb-4">
            <label className="text-fg-muted text-xs font-medium">Segment Prompt</label>
            <textarea name="ai_prompt" value={settings.ai_prompt || ''} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" rows="3" placeholder="Instructions..."></textarea>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-fg-muted text-xs font-medium">Metadata Prompt</label>
            <textarea name="ai_metadata_prompt" value={settings.ai_metadata_prompt || ''} onChange={handleChange} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" rows="3" placeholder="Output goals..."></textarea>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end mt-4">
          <button onClick={handleSave} className="bg-gradient-to-br from-violet-600 to-pink-600 text-white hover:from-violet-500 hover:to-rose-500 hover:-translate-y-0.5 hover:shadow-[0_6px_16px_rgba(139,92,246,0.4)] border-none rounded-lg py-3 px-6 font-semibold text-[15px] cursor-pointer transition-all duration-300 inline-flex items-center justify-center">Save Settings</button>
        </div>
        {toastVisible && <div className="text-center text-accent font-medium mt-2">Settings saved successfully!</div>}
      </div>
    </main>
  );
}
