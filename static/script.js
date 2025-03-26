function showSection(section) {
  // Toggle the active class for the sections
  document
    .getElementById("uploadSection")
    .classList.toggle("active", section === "upload");
  document
    .getElementById("downloadSection")
    .classList.toggle("active", section === "download");

  // Toggle the active class for the buttons
  document
    .getElementById("toggleUpload")
    .classList.toggle("active", section === "upload");
  document
    .getElementById("toggleDownload")
    .classList.toggle("active", section === "download");
}

// ✅ Render file list with remove option
function renderFileList(files) {
  let fileList = document.getElementById("fileList");
  fileList.innerHTML = ""; // Clear the existing list

  Array.from(files).forEach((file, index) => {
    let listItem = document.createElement("div");
    listItem.className = "file-item";

    let fileName = document.createElement("p");
    fileName.textContent = "📄 " + file.name;

    let removeButton = document.createElement("button");
    removeButton.textContent = "❌";
    removeButton.className = "remove-file";
    removeButton.onclick = () => {
      // Remove the file from the FileList
      let updatedFiles = Array.from(files);
      updatedFiles.splice(index, 1);
      updateFileInput(updatedFiles); // Update the input element
      renderFileList(updatedFiles); // Re-render the file list
    };

    listItem.appendChild(fileName);
    listItem.appendChild(removeButton);
    fileList.appendChild(listItem);
  });
}

// ✅ Update file input with new file list
function updateFileInput(files) {
  let dataTransfer = new DataTransfer();
  files.forEach((file) => dataTransfer.items.add(file));
  document.getElementById("fileInput").files = dataTransfer.files;
}

// ✅ Drag and Drop Support
let dropArea = document.getElementById("dropArea");
let fileInput = document.getElementById("fileInput");

dropArea.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropArea.classList.add("dragover");
});

dropArea.addEventListener("dragleave", () => {
  dropArea.classList.remove("dragover");
});

dropArea.addEventListener("drop", (event) => {
  event.preventDefault();
  dropArea.classList.remove("dragover");

  let files = event.dataTransfer.files;
  updateFileInput(Array.from(files)); // Update the file input with dropped files
  renderFileList(files); // Render the file list with remove options
});

// ✅ Handle file selection via "Select Files" button
fileInput.addEventListener("change", function () {
  renderFileList(this.files); // Render the file list with remove options
});

// ✅ Upload Files + Show File IDs
async function uploadFiles() {
  let files = document.getElementById("fileInput").files;
  let textContent = document.getElementById("textInput").value;
  let expirationPolicy = document.getElementById("expirationPolicy").value; // Get selected expiration policy
  let formData = new FormData();

  for (let file of files) {
    formData.append("files", file);
  }

  if (textContent) {
    formData.append("text_content", textContent);
  }

  formData.append("expiration_policy", expirationPolicy); // Add expiration policy to the form data

  // Show the loading screen
  let loadingScreen = document.getElementById("loadingScreen");
  let loadingText = document.getElementById("loadingText");
  let progressBar = document.getElementById("progress");
  loadingScreen.style.display = "flex";

  // Create XMLHttpRequest to track progress
  let xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload/", true);

  // Update progress bar
  xhr.upload.onprogress = function (event) {
    if (event.lengthComputable) {
      let percentComplete = Math.round((event.loaded / event.total) * 100);
      loadingText.textContent = `Uploading... ${percentComplete}%`;
      progressBar.style.width = `${percentComplete}%`;
    }
  };

  // Handle upload completion
  xhr.onload = function () {
    if (xhr.status === 200) {
      let result = JSON.parse(xhr.responseText);
      let uploadResult = document.getElementById("uploadResult");
      uploadResult.innerHTML = "";
      result.uploads.forEach((upload) => {
        let msg = document.createElement("p");
        msg.innerHTML = `✅ ${upload.message} - <b>ID: ${
          upload.file_id || upload.text_id
        }</b>`;
        uploadResult.appendChild(msg);
      });
    } else {
      alert("An error occurred during the upload.");
    }
    // Hide the loading screen
    loadingScreen.style.display = "none";
    progressBar.style.width = "0%";
    loadingText.textContent = "Uploading... 0%";
  };

  // Handle errors
  xhr.onerror = function () {
    alert("An error occurred during the upload.");
    loadingScreen.style.display = "none";
    progressBar.style.width = "0%";
    loadingText.textContent = "Uploading... 0%";
  };

  // Send the form data
  xhr.send(formData);
}

// ✅ Download File by ID
function downloadFile() {
  let fileId = document.getElementById("fileIdInput").value;
  if (!fileId) return alert("Enter a File ID!");
  window.location.href = "/download/" + fileId;
}
