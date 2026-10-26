export async function downloadFile(url: string, title: string) {
  const safeTitle = title
    .trim()
    .replace(/[^a-z0-9._ -]+/gi, "")
    .replace(/\s+/g, " ")
    .slice(0, 90) || "awaazify-cover";

  const response = await fetch(url);
  if (!response.ok) throw new Error("The MP3 download could not be started");

  const blobUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = `${safeTitle}.mp3`;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 30_000);
}
