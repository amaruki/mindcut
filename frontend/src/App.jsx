import React from 'react';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';

// Pages
import SettingsPage from './pages/Settings';
import UploadManagerPage from './pages/UploadManager';
import ChannelVideosPage from './pages/ChannelVideos';
import EditorStudioPage from './pages/EditorStudio';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<EditorStudioPage />} />
          <Route path="upload-manager" element={<UploadManagerPage />} />
          <Route path="scheduled" element={<ChannelVideosPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
