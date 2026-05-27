import { cpSync, rmSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const distDir = resolve(__dirname, 'dist')
const targetDir = resolve(__dirname, '..', 'xagent', 'src', 'xagent', 'resources', 'static')

if (!existsSync(distDir)) {
  console.error('dist directory not found. Run "npm run build" first.')
  process.exit(1)
}

if (existsSync(targetDir)) {
  rmSync(targetDir, { recursive: true, force: true })
}

cpSync(distDir, targetDir, { recursive: true })
console.log(`Deployed to ${targetDir}`)
