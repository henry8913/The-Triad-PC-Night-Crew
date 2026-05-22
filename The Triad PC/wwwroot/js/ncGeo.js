export async function getCurrentPosition() {
  if (!("geolocation" in navigator)) {
    throw new Error("Geolocalizzazione non supportata dal browser.");
  }

  return await new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        });
      },
      (err) => {
        reject(new Error(err?.message || "Permesso geolocalizzazione negato."));
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      }
    );
  });
}

// Facciamo anche da "global" per interop semplice (senza import JS isolation).
// Blazor: JS.InvokeAsync("ncGeo.getCurrentPosition")
globalThis.ncGeo = {
  getCurrentPosition,
};
