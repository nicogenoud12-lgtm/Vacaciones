// Simulación mínima de window.claude (db + downloads + user) para probar la página fuera de claude.ai.
// Solo para pruebas locales: se inyecta con Playwright antes de cargar la página.
(function () {
  const store = new Map(); // path -> data
  const listeners = new Set();
  let n = 0;
  const parent = (p) => p.split('/').slice(0, -1).join('/');
  const snapDoc = (path) => ({ id: path.split('/').pop(), exists: store.has(path), data: () => store.get(path), metadata: { fromCache: false, hasPendingWrites: false } });
  function emit() { for (const l of listeners) l(); }
  function docRef(path) {
    return {
      id: path.split('/').pop(), path,
      async get() { return snapDoc(path); },
      async set(d) { store.set(path, JSON.parse(JSON.stringify(d))); setTimeout(emit, 0); },
      async update(d) { if (!store.has(path)) throw { code: 'invalid_argument' }; store.set(path, Object.assign({}, store.get(path), JSON.parse(JSON.stringify(d)))); setTimeout(emit, 0); },
      async delete() { store.delete(path); setTimeout(emit, 0); },
      onSnapshot(next) { const l = () => next(snapDoc(path)); listeners.add(l); setTimeout(l, 5); return () => listeners.delete(l); },
      collection(sub) { return colRef(path + '/' + sub); },
    };
  }
  function colRef(path) {
    const docs = () => Array.from(store.keys()).filter((k) => parent(k) === path).sort().map(snapDoc);
    return {
      path,
      doc(id) { return docRef(path + '/' + (id || 'auto' + (++n) + Math.random().toString(36).slice(2, 6))); },
      async add(d) { const r = this.doc(); await r.set(d); return r; },
      async get() { const ds = docs(); return { docs: ds, size: ds.length, empty: !ds.length }; },
      onSnapshot(next) { const l = () => { const ds = docs(); next({ docs: ds, size: ds.length, empty: !ds.length, docChanges: () => [], metadata: { fromCache: false, hasPendingWrites: false } }); }; listeners.add(l); setTimeout(l, 5); return () => listeners.delete(l); },
    };
  }
  const db = { doc: docRef, collection: colRef };
  window.__mockStore = store;
  window.__downloads = [];
  const caps = {
    db,
    user: { can: async () => true, isOwner: async () => true, canEdit: async () => true },
    downloads: { save: async ({ filename, data }) => { let b64 = ''; try { const u = new Uint8Array(data); let s = ''; for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); b64 = btoa(s); } catch (e) {}
      window.__downloads.push({ filename, size: data.byteLength || data.length || data.size }); window.__files = window.__files || {}; window.__files[filename] = b64; return { status: 'saved' }; } },
  };
  window.claude = { use: async (name) => caps[name] || null };
  window.__seed = function (seed) {
    store.set('config/general', seed.config);
    for (const e of seed.empleados) { const d = Object.assign({}, e); delete d.id; store.set('empleados/' + e.id, d); }
    emit();
  };
})();
