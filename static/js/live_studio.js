let activeStream = null;
let logoPosition = 0;

async function startCamera(){
  try{
    stopMedia(false);
    activeStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: true
    });

    const video = document.getElementById("cameraPreview");
    video.srcObject = activeStream;
    video.style.display = "block";
    document.getElementById("emptyCamera").style.display = "none";
  }catch(err){
    alert("Camera blocked or unavailable. Please allow Camera/Microphone permission and reload. " + err.message);
  }
}

async function shareScreen(){
  try{
    stopMedia(false);
    activeStream = await navigator.mediaDevices.getDisplayMedia({
      video: { width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: true
    });

    const video = document.getElementById("cameraPreview");
    video.srcObject = activeStream;
    video.style.display = "block";
    document.getElementById("emptyCamera").style.display = "none";
  }catch(err){
    alert("Screen share could not start. " + err.message);
  }
}

function stopMedia(reset=true){
  if(activeStream){
    activeStream.getTracks().forEach(track => track.stop());
    activeStream = null;
  }

  if(reset){
    const video = document.getElementById("cameraPreview");
    const empty = document.getElementById("emptyCamera");
    if(video){
      video.srcObject = null;
      video.style.display = "none";
    }
    if(empty) empty.style.display = "grid";
  }
}

function moveLogo(){
  const logo = document.getElementById("chainLogo");
  logo.classList.remove("left","bottom");

  logoPosition = (logoPosition + 1) % 4;

  if(logoPosition === 1) logo.classList.add("left");
  if(logoPosition === 2) logo.classList.add("left","bottom");
  if(logoPosition === 3) logo.classList.add("bottom");
}

const mp3Input = document.getElementById("mp3Input");
if(mp3Input){
  mp3Input.addEventListener("change", function(){
    const name = this.files && this.files[0] ? this.files[0].name : "No file chosen";
    document.getElementById("fileName").innerText = name;
  });
}
