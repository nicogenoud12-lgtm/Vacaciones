// Arma la página publicable: inserta src/calc.js dentro de src/app.html.
// Uso: node build.mjs  ->  dist/vacaciones.html
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const calc = readFileSync(new URL('./src/calc.js', import.meta.url), 'utf8');
const app = readFileSync(new URL('./src/app.html', import.meta.url), 'utf8');
if (calc.includes('</script')) throw new Error('calc.js no puede contener </script>');
if (!app.includes('/*@@CALC@@*/')) throw new Error('Falta el marcador /*@@CALC@@*/ en app.html');
mkdirSync(new URL('./dist/', import.meta.url), { recursive: true });
const out = app.replace('/*@@CALC@@*/', () => calc);
writeFileSync(new URL('./dist/vacaciones.html', import.meta.url), out);
console.log('dist/vacaciones.html', out.length, 'bytes');
