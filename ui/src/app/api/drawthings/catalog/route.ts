import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { execFile } from 'child_process';
import { promisify } from 'util';

export const runtime = 'nodejs';

const execFileAsync = promisify(execFile);

function findRepoRoot(startDir: string): string {
  let currentDir = path.resolve(startDir);

  while (true) {
    if (fs.existsSync(path.join(currentDir, 'toolkit')) && fs.existsSync(path.join(currentDir, 'run.py'))) {
      return currentDir;
    }
    const parentDir = path.dirname(currentDir);
    if (parentDir === currentDir) {
      throw new Error(`Could not locate the ai-toolkit repository root from ${startDir}`);
    }
    currentDir = parentDir;
  }
}

function resolvePythonExecutable(repoRoot: string): string {
  const virtualEnv = process.env.VIRTUAL_ENV;
  const candidates = [
    virtualEnv ? path.join(virtualEnv, 'bin', 'python') : null,
    virtualEnv ? path.join(virtualEnv, 'Scripts', 'python.exe') : null,
    path.join(repoRoot, 'venv', 'bin', 'python'),
    path.join(repoRoot, 'venv', 'Scripts', 'python.exe'),
    path.join(repoRoot, '.venv', 'bin', 'python'),
    path.join(repoRoot, '.venv', 'Scripts', 'python.exe'),
    'python3',
    'python',
  ].filter(Boolean) as string[];

  for (const candidate of candidates) {
    if (!candidate.includes(path.sep) || fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error('Could not find a Python executable for Draw Things server probing.');
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const server = String(body?.server || '').trim();
    const port = Number(body?.port);
    const useTls = Boolean(body?.use_tls);
    const sharedSecret = String(body?.shared_secret || '').trim();

    if (server === '') {
      return NextResponse.json({ error: 'Server host or IP is required.' }, { status: 400 });
    }
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      return NextResponse.json({ error: 'Port must be an integer between 1 and 65535.' }, { status: 400 });
    }

    const repoRoot = findRepoRoot(process.cwd());
    const pythonExecutable = resolvePythonExecutable(repoRoot);
    const args = ['-m', 'toolkit.drawthings.probe_server', '--server', server, '--port', String(port)];

    if (useTls) {
      args.push('--use-tls');
    }
    if (sharedSecret !== '') {
      args.push('--shared-secret', sharedSecret);
    }

    const { stdout, stderr } = await execFileAsync(pythonExecutable, args, {
      cwd: repoRoot,
      maxBuffer: 10 * 1024 * 1024,
    });

    if (stderr && String(stderr).trim() !== '') {
      console.warn('Draw Things probe stderr:', String(stderr).slice(0, 4000));
    }

    const payload = JSON.parse(String(stdout || '{}'));
    return NextResponse.json({
      ok: Boolean(payload.ok),
      server: String(payload.server || server),
      port: Number(payload.port || port),
      requestedUseTls: Boolean(payload.requested_use_tls),
      resolvedUseTls: Boolean(payload.resolved_use_tls),
      files: Number(payload.files || 0),
      models: Array.isArray(payload.models) ? payload.models : [],
    });
  } catch (error: any) {
    const rawStderr = String(error?.stderr || '').trim();
    let message = error?.message || 'Failed to connect to the Draw Things server.';

    if (rawStderr !== '') {
      try {
        const parsed = JSON.parse(rawStderr);
        if (parsed?.error) {
          message = String(parsed.error);
        } else {
          message = rawStderr;
        }
      } catch {
        message = rawStderr;
      }
    }

    return NextResponse.json({ error: message }, { status: 500 });
  }
}
