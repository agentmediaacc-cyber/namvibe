/* === CREATE LIVE ROOM + REDIRECT === */

async function createAndGoLive() {
    if (!userMediaStream) {
        alert("Enable camera and mic first");
        return;
    }

    const payload = {
        title: document.getElementById("streamTitle")?.value || "Untitled Live",
        description: document.getElementById("streamDescription")?.value || "",
        audience: document.getElementById("streamAudience")?.value || "Public",
        room_access: document.getElementById("roomAccess")?.value || "Open Room",
        theme: document.getElementById("liveTheme")?.value || "theme-purple",
        quality: document.getElementById("streamQuality")?.value || "1280x720",
        frame_rate: parseInt(document.getElementById("frameRate")?.value || "30", 10),
        view_mode: document.getElementById("viewMode")?.value || "normal",
        allow_gifts: document.getElementById("allowGifts")?.checked ?? true,
        allow_comments: document.getElementById("allowComments")?.checked ?? true,
        allow_cohost: document.getElementById("allowCohost")?.checked ?? false,
        allow_premium_join: document.getElementById("allowPremiumJoin")?.checked ?? false,
        allow_premium_view: document.getElementById("allowPremiumView")?.checked ?? false,
        vip_badge: document.getElementById("vipBadge")?.checked ?? false,
        private_line: document.getElementById("privateLine")?.checked ?? false,
        location_text: document.getElementById("liveLocationText")?.innerText || ""
    };

    try {
        const resp = await fetch("/livestream/api/rooms/create/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify(payload)
        });

        const data = await resp.json();

        if (!data.ok) {
            alert("Error creating live room");
            console.error(data);
            return;
        }

        const room = data.room;

        // mark UI as live
        document.getElementById("streamStateBadge").textContent = "Live Now";
        document.getElementById("streamStateBadge").className = "live-status on";
        document.getElementById("liveModePill").textContent = "LIVE";

        // redirect to viewer page (real room)
        window.location.href = `/livestream/room/${room.id}/`;

    } catch (err) {
        console.error(err);
        alert("Network error creating live room");
    }
}

/* replace old startLiveNow */
function startLiveNow() {
    createAndGoLive();
}
