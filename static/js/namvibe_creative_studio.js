/* ── NAMVIBE CREATIVE STUDIO ── */
(function () {
  "use strict";

  var studioInstance = null;
  var currentTool = 'camera';
  var uploadedFile = null;
  var uploadedUrl = null;

  /* ── SVG Icons helper ── */
  function icon(path, view) {
    view = view || '0 0 24 24';
    return '<svg width="20" height="20" viewBox="' + view + '" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + path + '</svg>';
  }

  var TOOLS = [
    { id: 'camera', label: 'Camera', icon: icon('<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>') },
    { id: 'filters', label: 'Filters', icon: icon('<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>') },
    { id: 'adjust', label: 'Adjust', icon: icon('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>') },
    { id: 'ai', label: 'AI Edit', icon: icon('<path d="M12 2a4 4 0 0 0 0 8 4 4 0 0 0 0-8z"/><path d="M2 20v-2a6 6 0 0 1 6-6h8a6 6 0 0 1 6 6v2"/><circle cx="4" cy="4" r="2" fill="currentColor"/><circle cx="20" cy="4" r="2" fill="currentColor"/><circle cx="12" cy="22" r="2" fill="currentColor"/>') },
    { id: 'beauty', label: 'Beauty', icon: icon('<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>') },
    { id: 'crop', label: 'Crop', icon: icon('<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>') },
    { id: 'transform', label: 'Transform', icon: icon('<polyline points="1 4 1 10 7 10"/><polyline points="23 20 23 14 17 14"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/>') },
    { id: 'text', label: 'Text', icon: icon('<polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/>') },
    { id: 'stickers', label: 'Stickers', icon: icon('<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>') },
    { id: 'draw', label: 'Draw', icon: icon('<path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/>') },
    { id: 'music', label: 'Music', icon: icon('<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>') },
    { id: 'video', label: 'Video', icon: icon('<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>') },
    { id: 'effects', label: 'Effects', icon: icon('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/>') },
    { id: 'transitions', label: 'Transitions', icon: icon('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>') },
    { id: 'export', label: 'Export', icon: icon('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>') },
    { id: 'accessibility', label: 'Access', icon: icon('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>') }
  ];

  /* ── Build panel content per tool ── */
  function renderPanel(toolId) {
    switch (toolId) {
      case 'camera': return renderCameraPanel();
      case 'filters': return renderFiltersPanel();
      case 'adjust': return renderAdjustPanel();
      case 'ai': return renderAIPanel();
      case 'beauty': return renderBeautyPanel();
      case 'crop': return renderCropPanel();
      case 'transform': return renderTransformPanel();
      case 'text': return renderTextPanel();
      case 'stickers': return renderStickersPanel();
      case 'draw': return renderDrawPanel();
      case 'music': return renderMusicPanel();
      case 'video': return renderVideoPanel();
      case 'effects': return renderEffectsPanel();
      case 'transitions': return renderTransitionsPanel();
      case 'export': return renderExportPanel();
      case 'accessibility': return renderA11yPanel();
      default: return '<p style="color:var(--nv-cs-muted);font-size:13px;">Select a tool</p>';
    }
  }

  /* ── CAMERA MODES ── */
  function renderCameraPanel() {
    var modes = [
      { id: 'photo', label: 'Photo' }, { id: 'portrait', label: 'Portrait' },
      { id: 'selfie', label: 'Selfie' }, { id: 'night', label: 'Night' },
      { id: 'pro', label: 'Pro' }, { id: 'panorama', label: 'Panorama' },
      { id: 'hdr', label: 'HDR' }, { id: 'macro', label: 'Macro' },
      { id: 'ultrawide', label: 'Ultra Wide' }, { id: 'telephoto', label: 'Telephoto' },
      { id: 'slowmo', label: 'Slow Motion' }, { id: 'timelapse', label: 'Time Lapse' },
      { id: 'cinematic', label: 'Cinematic' }, { id: 'dual', label: 'Dual Camera' },
      { id: 'ai-cam', label: 'AI Camera' }, { id: 'scanner', label: 'Document' },
      { id: 'qr', label: 'QR Scanner' }
    ];
    var quality = [
      { label: '720p', val: '720p' }, { label: '1080p', val: '1080p' },
      { label: '2K', val: '2k' }, { label: '4K', val: '4k' }, { label: '8K', val: '8k' }
    ];
    var videoQ = [
      { label: '720p', val: '720p' }, { label: '1080p', val: '1080p' },
      { label: '2K', val: '2k' }, { label: '4K', val: '4k' },
      { label: '60 FPS', val: '60fps' }, { label: '120 FPS', val: '120fps' },
      { label: 'HDR', val: 'hdr' }
    ];
    return (
      '<div class="nv-cs-panel-section"><h4>Camera Mode</h4><div class="nv-cs-modes">' +
      modes.map(function (m) {
        return '<button class="nv-cs-mode-btn' + (m.id === 'photo' ? ' active' : '') + '" data-cs-mode="' + m.id + '">' +
          '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>' +
          m.label + '</button>';
      }).join('') +
      '</div></div>' +
      '<div class="nv-cs-panel-section"><h4>Photo Quality</h4><div class="nv-cs-quality">' +
      quality.map(function (q) {
        return '<button class="nv-cs-quality-btn' + (q.val === '1080p' ? ' active' : '') + '" data-cs-quality="' + q.val + '">' + q.label + '</button>';
      }).join('') +
      '</div></div>' +
      '<div class="nv-cs-panel-section"><h4>Video Quality</h4><div class="nv-cs-quality">' +
      videoQ.map(function (q) {
        return '<button class="nv-cs-quality-btn' + (q.val === '1080p' ? ' active' : '') + '" data-cs-vquality="' + q.val + '">' + q.label + '</button>';
      }).join('') +
      '</div></div>' +
      '<div class="nv-cs-panel-section"><button class="nv-cs-export-btn primary" data-cs-capture style="width:100%;padding:12px;margin-top:4px;">' +
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>' +
      'Open Camera</button></div>'
    );
  }

  /* ── FILTERS ── */
  function renderFiltersPanel() {
    var groups = [
      { name: 'Classic', filters: ['Original','Natural','Bright','Soft','Warm','Cool'] },
      { name: 'Instagram', filters: ['Clarendon','Gingham','Juno','Lark','Ludwig','Valencia','Sierra','Mayfair','Moon'] },
      { name: 'TikTok', filters: ['Vibe','Glow','Dream','Neon','Retro','Vintage','VHS'] },
      { name: 'Beauty', filters: ['Smooth Skin','Clear Skin','Face Glow','Makeup','Lip Color','Teeth Whitening','Eye Brightening'] },
      { name: 'Artistic', filters: ['Oil Painting','Watercolor','Sketch','Comic','Anime','Cartoon','Pencil','Pixel Art'] },
      { name: 'Professional', filters: ['Lightroom Style','Studio Portrait','HDR+','Cinematic','Golden Hour','Matte','Film'] }
    ];
    var html = '';
    groups.forEach(function (g) {
      html += '<div class="nv-cs-panel-section"><h4>' + g.name + '</h4><div class="nv-cs-filters">';
      g.filters.forEach(function (f) {
        html += '<button class="nv-cs-filter-btn" data-cs-filter="' + f + '">' +
          '<div class="nv-cs-filter-swatch"></div>' + f + '</button>';
      });
      html += '</div></div>';
    });
    return html;
  }

  /* ── ADJUST ── */
  function renderAdjustPanel() {
    var sliders = [
      'Brightness','Contrast','Saturation','Vibrance','Exposure',
      'Highlights','Shadows','Whites','Blacks','Sharpness',
      'Clarity','Texture','Temperature','Tint','Gamma',
      'Hue','Fade','Grain','Dehaze','Vignette'
    ];
    return sliders.map(function (s) {
      var id = s.toLowerCase().replace(/\s+/g, '-');
      return '<div class="nv-cs-slider-group"><label>' + s + ' <span id="cs-val-' + id + '">50</span></label>' +
        '<input type="range" class="nv-cs-slider" id="cs-slider-' + id + '" min="0" max="100" value="50" data-cs-adjust="' + id + '"></div>';
    }).join('');
  }

  /* ── AI EDITING ── */
  function renderAIPanel() {
    var tools = [
      'Auto Enhance','Remove Background','Blur Background','Sky Replacement',
      'Remove Objects','Remove People','Face Retouch','Beauty AI',
      'AI Portrait','AI Color Correction','AI Sharpen','AI Upscale',
      'AI Noise Removal','AI Relight'
    ];
    return '<div class="nv-cs-ai-grid">' +
      tools.map(function (t) {
        return '<button class="nv-cs-ai-btn" data-cs-ai="' + t + '">' +
          '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a4 4 0 0 0 0 8 4 4 0 0 0 0-8z"/><path d="M2 20v-2a6 6 0 0 1 6-6h8a6 6 0 0 1 6 6v2"/></svg>' +
          t + '</button>';
      }).join('') + '</div>';
  }

  /* ── BEAUTY ── */
  function renderBeautyPanel() {
    var features = [
      'Face Slimming','Nose Adjustment','Eye Enlargement','Jawline',
      'Skin Tone','Smooth Skin','Remove Acne','Remove Wrinkles',
      'Hair Color','Hair Style Preview'
    ];
    return '<div class="nv-cs-beauty-group">' +
      features.map(function (f) {
        return '<button class="nv-cs-beauty-btn" data-cs-beauty="' + f + '">' + f + '</button>';
      }).join('') + '</div>' +
      '<div class="nv-cs-slider-group"><label>Intensity <span id="cs-val-beauty">50</span></label>' +
      '<input type="range" class="nv-cs-slider" min="0" max="100" value="50" data-cs-adjust="beauty"></div>';
  }

  /* ── CROP ── */
  function renderCropPanel() {
    var crops = [
      { label: 'Free', icon: '⬜' }, { label: '1:1', icon: '⬛' },
      { label: '4:5', icon: '▯' }, { label: '9:16', icon: '▮' },
      { label: '16:9', icon: '▭' }, { label: '3:2', icon: '▬' },
      { label: 'Circle', icon: '⭕' }, { label: 'Story', icon: '📱' },
      { label: 'Reel', icon: '🎬' }, { label: 'Banner', icon: '🖼' }
    ];
    return '<div class="nv-cs-crops">' +
      crops.map(function (c) {
        return '<button class="nv-cs-crop-btn" data-cs-crop="' + c.label + '">' +
          '<span class="nv-cs-crop-icon"></span>' + c.label + '</button>';
      }).join('') + '</div>';
  }

  /* ── TRANSFORM ── */
  function renderTransformPanel() {
    var tools = ['Rotate','Flip','Perspective','Warp','Stretch','Scale','Mirror'];
    return '<div class="nv-cs-transform">' +
      tools.map(function (t) {
        return '<button class="nv-cs-transform-btn" data-cs-transform="' + t + '">' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><polyline points="23 20 23 14 17 14"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>' +
          t + '</button>';
      }).join('') + '</div>';
  }

  /* ── TEXT ── */
  function renderTextPanel() {
    var styles = ['Bold','Italic','Underline','Shadow','Outline','Glow','3D','Neon'];
    var fonts = ['Arial','Helvetica','Georgia','Times','Courier','Verdana','Trebuchet','Impact','Comic Sans','Monospace','Cursive','Fantasy'];
    return (
      '<div class="nv-cs-font-preview" id="csFontPreview">Your Text Here</div>' +
      '<div class="nv-cs-panel-section"><h4>Fonts</h4><div class="nv-cs-text-tools">' +
      fonts.map(function (f) {
        return '<button class="nv-cs-font-btn" data-cs-font="' + f + '" style="font-family:' + f + '">' + f + '</button>';
      }).join('') +
      '</div></div>' +
      '<div class="nv-cs-panel-section"><h4>Style</h4><div class="nv-cs-text-tools">' +
      styles.map(function (s) {
        return '<button class="nv-cs-text-style" data-cs-textstyle="' + s + '">' + s + '</button>';
      }).join('') +
      '</div></div>' +
      '<div class="nv-cs-panel-section"><button class="nv-cs-export-btn primary" data-cs-addtext style="width:100%;padding:10px;">Add Text</button></div>'
    );
  }

  /* ── STICKERS ── */
  function renderStickersPanel() {
    var categories = [
      { name: 'Emoji Stickers', items: ['😀','😂','😍','🥰','😎','🤩','🔥','💯','✨','⭐','❤️','💀','👋','🙌','🎉','🎊','💪','🫶','👑','🌟'] },
      { name: 'GIFs & Memes', items: ['😂','🤣','😭','😱','🥺','😤','💀','🗿','🌚','👏'] },
      { name: 'Time & Date', items: ['🕐','🕑','🕒','🕓','🕔','🕕','📅','📆','⏰','⌛'] },
      { name: 'Music & Media', items: ['🎵','🎶','🎤','🎧','🎸','🎹','🎬','📹','📸','🎥'] },
      { name: 'Location & Tags', items: ['📍','🗺','🏷','#️⃣','@','📌','🔖','💬','🔗','👤'] }
    ];
    var html = '';
    categories.forEach(function (cat) {
      html += '<div class="nv-cs-panel-section"><h4>' + cat.name + '</h4><div class="nv-cs-filters">';
      cat.items.forEach(function (s) {
        html += '<button class="nv-cs-effect-btn" data-cs-sticker="' + s + '">' + s + '<span>Sticker</span></button>';
      });
      html += '</div></div>';
    });
    return html;
  }

  /* ── DRAW ── */
  function renderDrawPanel() {
    var tools = ['Pen','Brush','Pencil','Marker','Spray','Neon Pen','Calligraphy'];
    var shapes = ['Line','Arrow','Rectangle','Circle','Triangle','Star','Heart'];
    var colors = ['#fff','#ec4899','#f472b6','#10b981','#3b82f6','#a855f7','#f59e0b','#ef4444','#8b5cf6','#06b6d4'];
    return (
      '<div class="nv-cs-panel-section"><h4>Tools</h4><div class="nv-cs-text-tools">' +
      tools.map(function (t) {
        return '<button class="nv-cs-draw-tool" data-cs-draw="' + t + '">' + t + '</button>';
      }).join('') +
      '</div></div>' +
      '<div class="nv-cs-panel-section"><h4>Shapes</h4><div class="nv-cs-text-tools">' +
      shapes.map(function (s) {
        return '<button class="nv-cs-draw-shape" data-cs-shape="' + s + '">' + s + '</button>';
      }).join('') +
      '</div></div>' +
      '<div class="nv-cs-panel-section"><h4>Color</h4><div class="nv-cs-quality">' +
      colors.map(function (c) {
        return '<button class="nv-cs-color-btn" data-cs-color="' + c + '" style="background:' + c + ';width:28px;height:28px;border-radius:50%;border:2px solid transparent;padding:0;cursor:pointer;"></button>';
      }).join('') +
      '</div></div>' +
      '<div class="nv-cs-slider-group"><label>Size <span id="cs-val-draw">3</span></label>' +
      '<input type="range" class="nv-cs-slider" min="1" max="20" value="3" data-cs-adjust="draw-size"></div>'
    );
  }

  /* ── MUSIC ── */
  function renderMusicPanel() {
    var tracks = [
      { name: 'Sunset Vibes', artist: 'NamVibe Originals', duration: '3:24' },
      { name: 'Ocean Waves', artist: 'NamVibe Originals', duration: '2:58' },
      { name: 'Neon Nights', artist: 'NamVibe Originals', duration: '4:12' },
      { name: 'Safari Groove', artist: 'NamVibe Originals', duration: '3:45' },
      { name: 'Windhoek Sunrise', artist: 'NamVibe Originals', duration: '3:02' },
      { name: 'Desert Star', artist: 'NamVibe Originals', duration: '5:30' }
    ];
    var html = '<div class="nv-cs-panel-section"><h4>Trending Tracks</h4>';
    tracks.forEach(function (t) {
      html += '<div class="nv-cs-music-item" data-cs-track="' + t.name + '">' +
        '<div class="nv-cs-music-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg></div>' +
        '<div class="nv-cs-music-info"><strong>' + t.name + '</strong><small>' + t.artist + ' · ' + t.duration + '</small></div>' +
        '<button class="nv-cs-quality-btn" data-cs-playtrack>▶</button></div>';
    });
    html += '</div>';
    html += '<div class="nv-cs-panel-section"><h4>Controls</h4>' +
      '<div class="nv-cs-quality"><button class="nv-cs-quality-btn" data-cs-trim>Trim</button>' +
      '<button class="nv-cs-quality-btn" data-cs-fadein>Fade In</button>' +
      '<button class="nv-cs-quality-btn" data-cs-fadeout>Fade Out</button>' +
      '<button class="nv-cs-quality-btn" data-cs-lyrics>Lyrics</button>' +
      '<button class="nv-cs-quality-btn" data-cs-beatsync>Beat Sync</button>' +
      '<button class="nv-cs-quality-btn" data-cs-voiceover>Voice Over</button>' +
      '<button class="nv-cs-quality-btn" data-cs-sfx>Sound FX</button></div></div>';
    return html;
  }

  /* ── VIDEO EDITING ── */
  function renderVideoPanel() {
    var tools = ['Trim','Split','Merge','Reverse','Speed Up','Slow Motion','Zoom In/Out','Rotate','Crop','Stabilize','Motion Blur','AI Captions','Auto Subtitle','Auto Translate'];
    return '<div class="nv-cs-ai-grid">' +
      tools.map(function (t) {
        return '<button class="nv-cs-ai-btn" data-cs-video="' + t + '">' +
          '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>' +
          t + '</button>';
      }).join('') + '</div>';
  }

  /* ── EFFECTS ── */
  function renderEffectsPanel() {
    var effects = [
      { emoji: '🔥', name: 'Fire' }, { emoji: '💨', name: 'Smoke' },
      { emoji: '❄️', name: 'Snow' }, { emoji: '🌧️', name: 'Rain' },
      { emoji: '⚡', name: 'Lightning' }, { emoji: '✨', name: 'Sparkles' },
      { emoji: '🎊', name: 'Confetti' }, { emoji: '💕', name: 'Hearts' },
      { emoji: '🫧', name: 'Bubbles' }, { emoji: '💜', name: 'Neon' },
      { emoji: '📺', name: 'Glitch' }, { emoji: '📼', name: 'VHS' },
      { emoji: '🪐', name: 'Hologram' }, { emoji: '🌞', name: 'Lens Flare' },
      { emoji: '🎆', name: 'Fireworks' }, { emoji: '🌊', name: 'Wave' }
    ];
    return '<div class="nv-cs-effects">' +
      effects.map(function (e) {
        return '<button class="nv-cs-effect-btn" data-cs-effect="' + e.name + '">' +
          e.emoji + '<span>' + e.name + '</span></button>';
      }).join('') + '</div>';
  }

  /* ── TRANSITIONS ── */
  function renderTransitionsPanel() {
    var trans = ['Fade','Slide','Zoom','Flip','Cube','Spin','Blur','Flash','Ripple','Morph'];
    return '<div class="nv-cs-transitions">' +
      trans.map(function (t) {
        return '<button class="nv-cs-trans-btn" data-cs-transition="' + t + '">' +
          '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>' +
          t + '</button>';
      }).join('') + '</div>';
  }

  /* ── EXPORT ── */
  function renderExportPanel() {
    return (
      '<div class="nv-cs-panel-section"><h4>Export Quality</h4><div class="nv-cs-quality">' +
      ['Save Draft','HD 720p','Full HD 1080p','2K','4K','Original Quality'].map(function (q) {
        return '<button class="nv-cs-quality-btn' + (q === 'Full HD 1080p' ? ' active' : '') + '" data-cs-exportq="' + q + '">' + q + '</button>';
      }).join('') +
      '</div></div>' +
      '<div class="nv-cs-panel-section"><h4>Options</h4><div class="nv-cs-export-grid">' +
      '<button class="nv-cs-export-btn" data-cs-watermark>' +
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>' +
      'Watermark ON</button>' +
      '<button class="nv-cs-export-btn" data-cs-savedraft>' +
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>' +
      'Save Draft</button></div></div>' +
      '<div class="nv-cs-panel-section" style="margin-top:12px;">' +
      '<button class="nv-cs-export-btn primary" data-cs-export style="width:100%;padding:14px;">' +
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>' +
      'Export & Publish</button></div>'
    );
  }

  /* ── ACCESSIBILITY ── */
  function renderA11yPanel() {
    var features = [
      'Voice Guidance','Large Text Mode','High Contrast Mode',
      'Auto Captions','Color-blind Friendly'
    ];
    return '<div class="nv-cs-a11y-grid">' +
      features.map(function (f) {
        return '<button class="nv-cs-a11y-btn" data-cs-a11y="' + f + '">' +
          '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>' +
          f + '</button>';
      }).join('') + '</div>';
  }

  /* ── Create/Open Studio ── */
  function openStudio(fileOrUrl) {
    if (studioInstance) {
      studioInstance.classList.add('active');
      return;
    }

    var modal = document.createElement('div');
    modal.className = 'nv-cs-modal';
    modal.innerHTML =
      '<div class="nv-cs-topbar">' +
      '<h2>' +
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>' +
      'Creative Studio</h2>' +
      '<button class="nv-cs-close-btn" id="csCloseBtn">✕</button></div>' +
      '<div class="nv-cs-toolbar" id="csToolbar"></div>' +
      '<div class="nv-cs-body">' +
      '<div class="nv-cs-preview" id="csPreview">' +
      '<div class="nv-cs-preview-empty">' +
      '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>' +
      '<p>Upload a photo or video to start editing<br><small style="color:var(--nv-cs-muted);">or use the camera</small></p>' +
      '</div></div>' +
      '<div class="nv-cs-panel" id="csPanel"></div></div>';

    document.body.appendChild(modal);
    studioInstance = modal;

    document.getElementById('csCloseBtn').addEventListener('click', closeStudio);

    /* Render toolbar */
    var tb = document.getElementById('csToolbar');
    tb.innerHTML = TOOLS.map(function (t) {
      return '<button class="nv-cs-tool-btn' + (t.id === currentTool ? ' active' : '') + '" data-cs-tool="' + t.id + '">' +
        t.icon + '<span>' + t.label + '</span></button>';
    }).join('');

    tb.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-cs-tool]');
      if (!btn) return;
      tb.querySelectorAll('.nv-cs-tool-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      currentTool = btn.dataset.csTool;
      document.getElementById('csPanel').innerHTML = renderPanel(currentTool);
      bindPanelEvents();
    });

    document.getElementById('csPanel').innerHTML = renderPanel(currentTool);
    bindPanelEvents();

    /* Handle file upload via drop / click */
    var preview = document.getElementById('csPreview');
    preview.addEventListener('dragover', function (e) { e.preventDefault(); preview.style.borderColor = 'var(--nv-cs-accent)'; });
    preview.addEventListener('dragleave', function () { preview.style.borderColor = ''; });
    preview.addEventListener('drop', function (e) {
      e.preventDefault();
      preview.style.borderColor = '';
      var file = e.dataTransfer.files[0];
      if (file) loadFile(file);
    });
    preview.addEventListener('click', function () {
      if (!uploadedFile) {
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*,video/*';
        input.onchange = function () { if (input.files[0]) loadFile(input.files[0]); };
        input.click();
      }
    });

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';

    if (fileOrUrl) loadFile(fileOrUrl);
  }

  function loadFile(file) {
    if (typeof file === 'string') {
      uploadedUrl = file;
      uploadedFile = { name: 'uploaded', type: 'image' };
    } else {
      uploadedFile = file;
      uploadedUrl = URL.createObjectURL(file);
    }
    var preview = document.getElementById('csPreview');
    var isVideo = uploadedFile && uploadedFile.type && uploadedFile.type.startsWith('video/');
    preview.innerHTML = isVideo
      ? '<video src="' + uploadedUrl + '" controls style="max-width:100%;max-height:100%;border-radius:4px;"></video>'
      : '<img src="' + uploadedUrl + '" alt="" style="max-width:100%;max-height:100%;border-radius:4px;object-fit:contain;">';
  }

  function bindPanelEvents() {
    var panel = document.getElementById('csPanel');
    if (!panel) return;

    panel.addEventListener('click', function (e) {
      var btn;

      /* Camera mode */
      btn = e.target.closest('[data-cs-mode]');
      if (btn) {
        panel.querySelectorAll('[data-cs-mode]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        return;
      }

      /* Quality */
      btn = e.target.closest('[data-cs-quality]');
      if (btn) {
        panel.querySelectorAll('[data-cs-quality]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        return;
      }
      btn = e.target.closest('[data-cs-vquality]');
      if (btn) {
        panel.querySelectorAll('[data-cs-vquality]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        return;
      }

      /* Filter */
      btn = e.target.closest('[data-cs-filter]');
      if (btn) {
        panel.querySelectorAll('[data-cs-filter]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        toast('Filter: ' + btn.dataset.csFilter);
        return;
      }

      /* AI */
      btn = e.target.closest('[data-cs-ai]');
      if (btn) {
        btn.classList.add('active');
        setTimeout(function () { btn.classList.remove('active'); }, 1500);
        toast('AI: ' + btn.dataset.csAi);
        return;
      }

      /* Beauty */
      btn = e.target.closest('[data-cs-beauty]');
      if (btn) {
        btn.classList.toggle('active');
        return;
      }

      /* Crop */
      btn = e.target.closest('[data-cs-crop]');
      if (btn) {
        panel.querySelectorAll('[data-cs-crop]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        toast('Crop: ' + btn.dataset.csCrop);
        return;
      }

      /* Transform */
      btn = e.target.closest('[data-cs-transform]');
      if (btn) {
        toast('Transform: ' + btn.dataset.csTransform);
        return;
      }

      /* Font */
      btn = e.target.closest('[data-cs-font]');
      if (btn) {
        panel.querySelectorAll('[data-cs-font]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        var fp = document.getElementById('csFontPreview');
        if (fp) fp.style.fontFamily = btn.dataset.csFont;
        return;
      }

      /* Text style */
      btn = e.target.closest('[data-cs-textstyle]');
      if (btn) {
        btn.classList.toggle('active');
        var fp = document.getElementById('csFontPreview');
        if (fp) {
          var s = btn.dataset.csTextstyle.toLowerCase();
          if (s === 'shadow') fp.style.textShadow = '2px 2px 4px rgba(0,0,0,.5)';
          else if (s === 'glow') fp.style.textShadow = '0 0 10px var(--nv-cs-accent)';
          else if (s === 'neon') fp.style.textShadow = '0 0 5px #fff, 0 0 10px var(--nv-cs-accent), 0 0 20px var(--nv-cs-accent)';
          else if (s === 'outline') fp.style.webkitTextStroke = '1px var(--nv-cs-accent)';
          else if (s === 'bold') fp.style.fontWeight = fp.style.fontWeight === '700' ? '400' : '700';
          else if (s === 'italic') fp.style.fontStyle = fp.style.fontStyle === 'italic' ? 'normal' : 'italic';
          else if (s === 'underline') fp.style.textDecoration = fp.style.textDecoration === 'underline' ? 'none' : 'underline';
          else if (s === '3d') fp.style.textShadow = '1px 1px 0 var(--nv-cs-muted), 2px 2px 0 var(--nv-cs-muted), 3px 3px 0 var(--nv-cs-muted)';
        }
        return;
      }

      /* Add text */
      btn = e.target.closest('[data-cs-addtext]');
      if (btn) {
        toast('Text added! ✏️');
        return;
      }

      /* Sticker */
      btn = e.target.closest('[data-cs-sticker]');
      if (btn) {
        toast('Sticker: ' + btn.dataset.csSticker);
        return;
      }

      /* Draw tool */
      btn = e.target.closest('[data-cs-draw]');
      if (btn) {
        panel.querySelectorAll('[data-cs-draw]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        return;
      }

      /* Draw shape */
      btn = e.target.closest('[data-cs-shape]');
      if (btn) {
        toast('Shape: ' + btn.dataset.csShape);
        return;
      }

      /* Color */
      btn = e.target.closest('[data-cs-color]');
      if (btn) {
        panel.querySelectorAll('[data-cs-color]').forEach(function (b) { b.style.borderColor = 'transparent'; });
        btn.style.borderColor = 'var(--nv-cs-accent)';
        return;
      }

      /* Music track */
      btn = e.target.closest('[data-cs-track]');
      if (btn) {
        toast('Added: ' + btn.dataset.csTrack);
        return;
      }
      btn = e.target.closest('[data-cs-playtrack]');
      if (btn) {
        btn.textContent = btn.textContent === '▶' ? '⏸' : '▶';
        return;
      }

      /* Music controls */
      if (e.target.closest('[data-cs-trim]')) { toast('Trim mode'); return; }
      if (e.target.closest('[data-cs-fadein]')) { toast('Fade In applied'); return; }
      if (e.target.closest('[data-cs-fadeout]')) { toast('Fade Out applied'); return; }
      if (e.target.closest('[data-cs-lyrics]')) { toast('Lyrics view'); return; }
      if (e.target.closest('[data-cs-beatsync]')) { toast('Beat Sync active'); return; }
      if (e.target.closest('[data-cs-voiceover]')) { toast('Voice Over ready'); return; }
      if (e.target.closest('[data-cs-sfx]')) { toast('Sound Effects library'); return; }

      /* Video tools */
      btn = e.target.closest('[data-cs-video]');
      if (btn) {
        toast('Video: ' + btn.dataset.csVideo);
        return;
      }

      /* Effects */
      btn = e.target.closest('[data-cs-effect]');
      if (btn) {
        panel.querySelectorAll('[data-cs-effect]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        toast('Effect: ' + btn.dataset.csEffect);
        return;
      }

      /* Transitions */
      btn = e.target.closest('[data-cs-transition]');
      if (btn) {
        panel.querySelectorAll('[data-cs-transition]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        toast('Transition: ' + btn.dataset.csTransition);
        return;
      }

      /* Export quality */
      btn = e.target.closest('[data-cs-exportq]');
      if (btn) {
        panel.querySelectorAll('[data-cs-exportq]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        return;
      }

      /* Watermark */
      btn = e.target.closest('[data-cs-watermark]');
      if (btn) {
        btn.textContent = btn.textContent.includes('ON') ? 'Watermark OFF' : 'Watermark ON';
        return;
      }

      /* Save draft */
      btn = e.target.closest('[data-cs-savedraft]');
      if (btn) {
        toast('Draft saved! 💾');
        return;
      }

      /* Export */
      btn = e.target.closest('[data-cs-export]');
      if (btn) {
        toast('Exporting... 🚀');
        closeStudio();
        return;
      }

      /* Accessibility */
      btn = e.target.closest('[data-cs-a11y]');
      if (btn) {
        btn.classList.toggle('active');
        toast('Accessibility: ' + btn.dataset.csA11y + ' ' + (btn.classList.contains('active') ? 'ON' : 'OFF'));
        return;
      }

      /* Camera capture */
      if (e.target.closest('[data-cs-capture]')) {
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*,video/*';
        input.capture = 'environment';
        input.onchange = function () { if (input.files[0]) loadFile(input.files[0]); };
        input.click();
      }
    });

    /* Slider events */
    panel.addEventListener('input', function (e) {
      var slider = e.target.closest('[data-cs-adjust]');
      if (!slider) return;
      var val = slider.value;
      var label = document.getElementById('cs-val-' + slider.dataset.csAdjust);
      if (label) label.textContent = val;
      /* Apply filter preview via CSS filter */
      var preview = document.getElementById('csPreview');
      if (preview && uploadedUrl) {
        var img = preview.querySelector('img, video');
        if (img) {
          var brightness = parseInt(document.getElementById('cs-val-brightness')?.textContent || '50', 10);
          var contrast = parseInt(document.getElementById('cs-val-contrast')?.textContent || '50', 10);
          var sat = parseInt(document.getElementById('cs-val-saturation')?.textContent || '50', 10);
          var blur = parseInt(document.getElementById('cs-val-sharpness')?.textContent || '50', 10);
          img.style.filter = 'brightness(' + (brightness / 50) + ') contrast(' + (contrast / 50) + ') saturate(' + (sat / 50) + ')';
        }
      }
    });
  }

  function closeStudio() {
    if (studioInstance) {
      studioInstance.classList.remove('active');
      setTimeout(function () {
        if (studioInstance && studioInstance.parentNode) studioInstance.parentNode.removeChild(studioInstance);
        studioInstance = null;
        document.body.style.overflow = '';
      }, 250);
    }
  }

  function toast(msg) {
    if (window.NamVibeToast && window.NamVibeToast.show)
      window.NamVibeToast.success(msg);
  }

  window.NamVibeCreativeStudio = {
    open: openStudio,
    close: closeStudio
  };

})();
