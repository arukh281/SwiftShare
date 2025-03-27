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
  const textInput = document.getElementById("textInput").value.trim();
  const expirationPolicy = document.getElementById("expirationPolicy").value;
  const uploadResult = document.getElementById("uploadResult");

  try {
    const formData = new FormData();
    formData.append("expiration_policy", expirationPolicy);

    if (textInput) {
      formData.append("text_content", textInput);
    }

    // Add files if present
    const fileInput = document.getElementById("fileInput");
    if (fileInput && fileInput.files.length > 0) {
      for (const file of fileInput.files) {
        formData.append("files", file);
      }
    }

    const response = await fetch("/upload/", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    if (data.uploads && data.uploads.length > 0) {
      const fileId = data.uploads[0].file_id;
      uploadResult.textContent = `Upload successful! Your file ID is: ${fileId}`;
    }
  } catch (error) {
    uploadResult.textContent = "Error uploading: " + error.message;
    console.error("Upload error:", error);
  }
}

// ✅ Download File by ID
async function downloadFile() {
  const fileId = document.getElementById("fileIdInput").value.trim();
  const downloadResult = document.getElementById("downloadResult");

  if (!fileId) {
    downloadResult.textContent = "Please enter a file ID";
    return;
  }

  try {
    // Show loading state
    downloadResult.textContent = "Downloading...";

    const response = await fetch(`/download/${fileId}`);
    const contentType = response.headers.get("content-type");

    // Handle JSON responses (errors)
    if (contentType && contentType.includes("application/json")) {
      const data = await response.json();
      downloadResult.textContent = data.error || "Error downloading file";
      return;
    }

    // Handle successful file download
    if (response.ok) {
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      const filename =
        response.headers
          .get("content-disposition")
          ?.split("filename=")[1]
          ?.replace(/"/g, "") || "downloaded-file";

      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      downloadResult.textContent = "Download successful!";

      // Clear success message after 3 seconds
      setTimeout(() => {
        downloadResult.textContent = "";
      }, 3000);
    } else {
      downloadResult.textContent = "Error downloading file";
    }
  } catch (error) {
    console.error("Download error:", error);
    downloadResult.textContent = "Error downloading file";
  }
}
