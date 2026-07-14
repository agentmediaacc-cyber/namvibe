/* ── NamVibe Unicode Emoji Picker ── */
(function () {
  "use strict";

  var EMOJI_CATEGORIES = [
    {
      name: 'Smileys',
      icon: '😀',
      emojis: [
        '😀','😃','😄','😁','😆','😅','😂','🤣','😊','😇','🙂','🙃','😉','😌','😍','🥰','😘','😗','😙','😚','😋','😛','😜','🤪','😝','🤑','🤗','🤭','🫢','🫣','🤫','🤔','🫡','🤐','🤨','😐','😑','😶','🫥','😏','😒','🙄','😬','😮','😯','😲','😳','🥺','😦','😧','😨','😰','😥','😢','😭','😱','😖','😣','😞','😓','😩','😫','🥱','😤','😡','😠','🤬','😈','👿','💀','☠','💩','🤡','👹','👺','👻','👽','👾','🤖','😺','😸','😹','😻','😼','😽','🙀','😿','😾','🫶','🤲','🙌','👏','🤝','👍','👎','👊','✊','🤛','🤜','👋','🤚','✋','🖐','✌','🤞','🫰','🫵','🫱','🫲','🫳','🫴','🤟','🤘','🤙','👌','🤌','🫳','🫴','❤','🩷','🧡','💛','💚','💙','🩵','💜','🖤','🩶','🤍','🤎','💔','❤️‍🔥','❤️‍🩹','❣','💕','💞','💓','💗','💖','💘','💝','💟','♥','🫶','💯','✨','⭐','🌟','💫','🔥'
      ]
    },
    {
      name: 'People',
      icon: '👋',
      emojis: [
        '👋','🤚','🖐','✋','🖐','✌','🤞','🫰','🫵','🫱','🫲','🫳','🫴','🤟','🤘','🤙','👌','🤌','🤏','🫳','🫴','✌','🤞','🤟','🤘','🤙','👈','👉','👆','🖕','👇','☝','👍','👎','✊','👊','🤛','🤜','👏','🙌','🫶','👐','🤲','🤝','🙏','✍','💅','🤳','💪','🦾','🦵','🦿','🦶','👣','👂','🦻','👃','🧠','🫀','🫁','🦷','🦴','👀','👁','👅','👄','🫦','👶','🧒','👦','👧','🧑','👱','👨','👩','🧔','👨‍🦰','👨‍🦱','👨‍🦳','👨‍🦲','👩‍🦰','👩‍🦱','👩‍🦳','👩‍🦲','👴','👵','🧓','🙍','🙎','🙅','🙆','💁','🙋','🧏','🙇','🤦','🤷','👮','🕵','💂','🥷','👷','🫅','🤴','👸','👳','👲','🧕','🤵','👰','🤰','🫃','🫄','🤱','👩‍🍼','👨‍🍼','🧑‍🍼','👼','🎅','🤶','🧑‍🎄','🦸','🦹','🧙','🧝','🧛','🧟','🧞','🧜','🧚','🧌'
      ]
    },
    {
      name: 'Animals',
      icon: '🐶',
      emojis: [
        '🐶','🐱','🦁','🐯','🐼','🐻','🐻‍❄','🦊','🐨','🐵','🙈','🙉','🙊','🐸','🐒','🦍','🦧','🐺','🐗','🐴','🦄','🫎','🫏','🐝','🐛','🦋','🐌','🐞','🐜','🦟','🦗','🪰','🪱','🐢','🐍','🦎','🦖','🦕','🐙','🦑','🪼','🦐','🦞','🦀','🐡','🐠','🐟','🐬','🐳','🐋','🦈','🪸','🐊','🐅','🐆','🦓','🦍','🦧','🐘','🦣','🦛','🦏','🐪','🐫','🦒','🦘','🦬','🐃','🐂','🐄','🐎','🐖','🐏','🐑','🦙','🐐','🦌','🐕','🐩','🦮','🐕‍🦺','🐈','🐈‍⬛','🪶','🐓','🦃','🦤','🦚','🦜','🦢','🦩','🕊','🐇','🦝','🦨','🦡','🦫','🦦','🦥','🐁','🐀','🐿','🦔','🐾','🐉','🐲','🦅','🦉','🦇','🐧','🐦','🐤','🐣','🐥','🪿','🦆','🐸'
      ]
    },
    {
      name: 'Food',
      icon: '🍕',
      emojis: [
        '🍕','🍔','🍟','🌭','🌮','🌯','🫓','🥪','🥙','🧆','🥚','🍳','🥘','🍲','🫕','🥣','🥗','🍿','🧈','🧂','🥫','🍱','🍘','🍙','🍚','🍛','🍜','🍝','🍠','🍢','🍣','🍤','🍥','🥮','🍡','🥟','🥠','🥡','🦪','🍦','🍧','🍨','🍩','🍪','🎂','🍰','🧁','🥧','🍫','🍬','🍭','🍮','🍯','🍼','🥛','☕','🫖','🍵','🍶','🍾','🍷','🍸','🍹','🍺','🍻','🥂','🥃','🫗','🧊','🥤','🧋','🍴','🥄','🔪','🫙','🏺'
      ]
    },
    {
      name: 'Activities',
      icon: '⚽',
      emojis: [
        '⚽','🏀','🏈','⚾','🎾','🏐','🏉','🥏','🎱','🪀','🏓','🏸','🏒','🏑','🥍','🏏','🪃','🥅','⛳','🪁','🏹','🎣','🤿','🥊','🥋','🎽','🛹','🛼','🛷','⛸','🥌','🎿','⛷','🏂','🪂','🏋','🤼','🤸','🤺','⛹','🤾','🏌','🏇','🧘','🏄','🏊','🤽','🚣','🏆','🥇','🥈','🥉','🏅','🎖','🏵','🎗','🎫','🎟','🎪','🤹','🎭','🎨','🎬','🎤','🎧','🎼','🎹','🥁','🪘','🎷','🎺','🪗','🎸','🪕','🎻','🎲','♟','🎯','🎳','🎮','🕹','🎰','🧩'
      ]
    },
    {
      name: 'Travel',
      icon: '🚗',
      emojis: [
        '🚗','🚕','🚙','🚌','🚎','🏎','🚓','🚑','🚒','🚐','🛻','🚚','🚛','🚜','🏍','🛵','🛺','🦽','🦼','🛴','🚲','🛹','🛼','🚏','🛣','🛤','⛽','🛞','🚨','🚥','🚦','🛑','🚧','⚓','🛟','⛵','🛶','🚤','🛳','⛴','🛥','🚢','✈','🛩','🛫','🛬','🪂','💺','🚁','🚟','🚠','🚡','🛰','🚀','🛸','🏠','🏡','🏘','🏚','🏗','🏢','🏣','🏤','🏥','🏦','🏨','🏩','🏪','🏫','🏬','🏭','🏯','🏰','💒','🗼','🗽','⛪','🕌','🛕','🕍','⛩','🕋','⛲','⛺','🌁','🌃','🏙','🌄','🌅','🌆','🌇','🌉','🗾','🏔','⛰','🌋','🗻','🏕','🏖','🏜','🏝','🏞'
      ]
    },
    {
      name: 'Objects',
      icon: '💎',
      emojis: [
        '💎','💰','💳','📱','💻','⌚','🎁','📷','🎥','🔥','💡','🔦','🏮','🪔','📔','📕','📖','📗','📘','📙','📚','📓','📒','📃','📜','📄','📰','🗞','📑','🔖','🏷','💰','🪙','💴','💵','💶','💷','🪪','💳','🧾','✉','📧','📨','📩','📤','📥','📦','📫','📪','📬','📭','📮','🗳','✏','✒','🖋','🖊','🖌','🖍','📝','💼','📁','📂','🗂','📅','📆','🗒','🗓','📇','📈','📉','📊','📋','📌','📍','📎','🖇','📏','📐','✂','🗃','🗄','🗑','🔑','🗝','🔨','🪓','⛏','⚒','🛠','🗡','⚔','💣','🪃','🏹','🛡','🔧','🪛','🔩','⚙','🗜','⚖','🦯','🔗','⛓','🪝','🧰','🧲','🪜','🔬','🔭','📡','💉','🩸','💊','🩹','🩺','🚿','🛁','🛀','🧴','🧷','🧹','🧺','🧻','🪣','🧽','🧼','🪥','🪒','🪮','🧯','🛒'
      ]
    },
    {
      name: 'Symbols',
      icon: '❤️',
      emojis: [
        '❤','🩷','🧡','💛','💚','💙','🩵','💜','🖤','🩶','🤍','🤎','💔','❤️‍🔥','❤️‍🩹','❣','💕','💞','💓','💗','💖','💘','💝','💟','♥','💯','✔','✖','➕','➖','➗','🟰','♾','💲','💱','🔃','🔄','🆕','🆙','🆒','🆓','🆖','🆗','🆙','🆚','🈁','🈂','🈷','🈶','🈯','🉐','🈹','🈚','🈲','🈴','🈵','🈳','🈸','🈺','🉑','🎦','🏧','🚮','🚰','♿','🚹','🚺','🚻','🚼','🚾','🛂','🛃','🛄','🛅','⚠','🚸','⛔','🚫','🚳','🚭','🚯','🚱','🚷','📵','🔞','☢','☣','⬆','⬇','⬅','➡','↗','↘','↙','↖','↕','↔','🔄','↩','↪','⤴','⤵','🔃','🔄','🔙','🔚','🔛','🔜','🔝','🛐','⚛','🕉','✡','☸','☯','✝','☦','☪','☮','🕎','🔯','♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓','⛎','🔀','🔁','🔂','▶','⏩','⏭','⏯','◀','⏪','⏮','🔼','⏫','🔽','⏬','⏸','⏹','⏺','⏏','🎦','🔅','🔆','📶','📳','📴','♻','📛','🔰','🔱','⭕','✅','☑','✔','❌','❎','➰','➿','〽','✳','✴','❇','‼','⁉','❓','❔','❕','❗','〰','©','®','™','#️⃣','*️⃣','0️⃣','1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟','🔠','🔡','🔢','🔣','🔤','🅰','🆎','🅱','🆑','🆒','🆓','ℹ','🆔','Ⓜ','🆕','🆖','🅾','🆗','🅿','🆘','🆙','🆚','🈁','🈂','🈷','🈶','🈯','🉐','🈹','🈚','🈲','🈴','🈵','🈳','🈸','🈺','🉑'
      ]
    },
    {
      name: 'Flags',
      icon: '🇳🇦',
      emojis: [
        '🇳🇦','🇿🇦','🇧🇼','🇦🇴','🇺🇸','🇬🇧','🇫🇷','🇩🇪','🇯🇵','🇨🇳','🇮🇳','🇧🇷','🇨🇦','🇦🇺','🇷🇺','🇰🇷','🇸🇪','🇳🇴','🇩🇰','🇫🇮','🇮🇸','🇪🇸','🇮🇹','🇵🇹','🇬🇷','🇹🇷','🇳🇱','🇧🇪','🇨🇭','🇦🇹','🇮🇪','🇵🇱','🇨🇿','🇭🇺','🇷🇴','🇧🇬','🇺🇦','🇮🇱','🇸🇦','🇦🇪','🇸🇬','🇭🇰','🇹🇼','🇦🇷','🇨🇱','🇨🇴','🇵🇪','🇪🇬','🇰🇪','🇳🇬','🇬🇭','🇲🇦','🇹🇳','🇩🇿','🇪🇹','🇹🇿','🇺🇬','🇿🇲','🇿🇼','🇲🇼','🇲🇿','🇦🇴','🇨🇲','🇨🇮','🇸🇳','🇲🇱','🇧🇫','🇳🇪','🇹🇩','🇸🇩','🇲🇬','🇷🇼','🇸🇴','🇱🇾','🇲🇷','🇧🇯','🇸🇱','🇹🇬','🇱🇷','🇲🇺','🇨🇻','🇸🇨','🇰🇲','🇲🇺','🇸🇹','🇬🇼','🇬🇶','🇨🇫','🇨🇬','🇩🇯','🇪🇷','🇸🇿','🇱🇸','🇧🇮','🇰🇲','🇾🇹','🇷🇪','🇸🇭','🇮🇴',
        '🏴','🏳','🏴‍☠','🇺🇳','🇪🇺'
      ]
    }
  ];

  var SKIN_TONES = [
    { name: 'Default', color: '#FFCC22' },
    { name: 'Light', color: '#F5D3B0' },
    { name: 'Medium-Light', color: '#E0AC69' },
    { name: 'Medium', color: '#C88A4F' },
    { name: 'Medium-Dark', color: '#A06A3B' },
    { name: 'Dark', color: '#6B4226' }
  ];

  var currentSkinTone = 0;
  var pickerInstance = null;
  var onSelectCallback = null;
  var activeInput = null;

  function createEmojiPicker() {
    if (pickerInstance) return pickerInstance;

    var container = document.createElement('div');
    container.className = 'nv-emoji-picker';
    container.innerHTML =
      '<div class="nv-ep-header" id="epCategories"></div>' +
      '<div class="nv-ep-search"><input type="text" id="epSearch" placeholder="Search emojis..." /></div>' +
      '<div class="nv-ep-body" id="epBody"></div>' +
      '<div class="nv-ep-footer">' +
      '<div class="nv-ep-preview" id="epPreview">😀</div>' +
      '<div class="nv-ep-skin-tone" id="epSkinTones"></div>' +
      '</div>';

    document.body.appendChild(container);
    pickerInstance = container;

    var activeCategory = 0;
    var header = container.querySelector('#epCategories');
    var body = container.querySelector('#epBody');
    var search = container.querySelector('#epSearch');
    var preview = container.querySelector('#epPreview');
    var skinTones = container.querySelector('#epSkinTones');

    skinTones.innerHTML = SKIN_TONES.map(function (st, i) {
      return '<button class="' + (i === currentSkinTone ? 'active' : '') + '" data-skin="' + i + '" style="background:' + st.color + '" title="' + st.name + '"></button>';
    }).join('');

    skinTones.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-skin]');
      if (!btn) return;
      currentSkinTone = parseInt(btn.dataset.skin, 10);
      skinTones.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      renderCategory(activeCategory);
    });

    function renderCategory(index) {
      activeCategory = index;
      header.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
      header.children[index].classList.add('active');
      var cat = EMOJI_CATEGORIES[index];
      body.innerHTML = '<div class="nv-ep-category-label">' + cat.name + '</div>' +
        cat.emojis.map(function (e) {
          return '<button class="nv-ep-emoji" data-emoji="' + e + '">' + e + '</button>';
        }).join('');
    }

    function renderSearch(query) {
      if (!query) {
        renderCategory(activeCategory);
        return;
      }
      var lower = query.toLowerCase();
      var results = [];
      EMOJI_CATEGORIES.forEach(function (cat) {
        cat.emojis.forEach(function (e) {
          if (e.toLowerCase().includes(lower)) results.push(e);
        });
      });
      if (results.length === 0) {
        body.innerHTML = '<div style="padding:20px;color:var(--nv-ep-muted);text-align:center;width:100%;font-size:13px;">No emojis found</div>';
        return;
      }
      body.innerHTML = results.map(function (e) {
        return '<button class="nv-ep-emoji" data-emoji="' + e + '">' + e + '</button>';
      }).join('');
    }

    header.innerHTML = EMOJI_CATEGORIES.map(function (c, i) {
      return '<button class="' + (i === 0 ? 'active' : '') + '" data-cat="' + i + '" title="' + c.name + '">' + c.icon + '</button>';
    }).join('');

    header.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-cat]');
      if (!btn) return;
      renderCategory(parseInt(btn.dataset.cat, 10));
      search.value = '';
    });

    search.addEventListener('input', function () {
      renderSearch(this.value.trim());
    });

    body.addEventListener('click', function (e) {
      var btn = e.target.closest('.nv-ep-emoji');
      if (!btn) return;
      var emoji = btn.dataset.emoji;
      preview.textContent = emoji;
      if (onSelectCallback) {
        onSelectCallback(emoji, activeInput);
      }
    });

    body.addEventListener('mouseover', function (e) {
      var btn = e.target.closest('.nv-ep-emoji');
      if (btn) preview.textContent = btn.dataset.emoji;
    });

    container.addEventListener('click', function (e) {
      e.stopPropagation();
    });

    document.addEventListener('click', function () {
      hideEmojiPicker();
    });

    renderCategory(0);
    return container;
  }

  function showEmojiPicker(anchorEl, callback, inputEl) {
    var picker = createEmojiPicker();
    onSelectCallback = callback;
    activeInput = inputEl || null;

    var rect = anchorEl.getBoundingClientRect();
    var pickerW = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nv-ep-width').trim(), 10) || 340;
    var spaceBelow = window.innerHeight - rect.bottom;
    var spaceAbove = rect.top;
    var pickerH = 400;

    if (spaceBelow > pickerH || spaceBelow > spaceAbove) {
      picker.style.top = (rect.bottom + 6) + 'px';
      picker.style.bottom = 'auto';
    } else {
      picker.style.bottom = (window.innerHeight - rect.top + 6) + 'px';
      picker.style.top = 'auto';
    }

    var left = Math.max(8, Math.min(rect.left, window.innerWidth - pickerW - 8));
    picker.style.left = left + 'px';
    picker.classList.add('active');
  }

  function hideEmojiPicker() {
    if (pickerInstance) {
      pickerInstance.classList.remove('active');
    }
    onSelectCallback = null;
    activeInput = null;
  }

  window.NamVibeEmojiPicker = {
    show: showEmojiPicker,
    hide: hideEmojiPicker,
    getPicker: createEmojiPicker
  };

})();
