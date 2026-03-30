import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();
const isWindows = process.platform === 'win32';

export async function GET(request: NextRequest, { params }: { params: { jobID: string } }) {
  const { jobID } = await params;

  const job = await prisma.job.findUnique({
    where: { id: jobID },
  });

  if (!job) {
    return NextResponse.json({ error: 'Job not found' }, { status: 404 });
  }

  let updatedJob = await prisma.job.update({
    where: { id: jobID },
    data: {
      stop: true,
      status: 'stopping',
      info: 'Stopping job...',
    },
  });

  // Send SIGINT to the process if we have a PID
  if (job.pid != null) {
    console.log(`Attempting to stop job ${jobID} with PID ${job.pid}`);
    try {
      if (isWindows) {
        // Windows doesn't support SIGINT for arbitrary processes.
        // Use taskkill with /T (tree) to send a CTRL+C-like termination.
        const { execSync } = require('child_process');
        execSync(`taskkill /PID ${job.pid} /T /F`, { stdio: 'ignore' });
      } else {
        process.kill(job.pid, 'SIGINT');
      }
    } catch (e: any) {
      // Process may have already exited — that's fine
      console.error('Error sending signal to process:', e);
      if (e?.code === 'ESRCH') {
        updatedJob = await prisma.job.update({
          where: { id: jobID },
          data: {
            status: 'stopped',
            stop: false,
            return_to_queue: false,
            pid: null,
            info: 'Job stopped',
          },
        });
      }
    }
  } else {
    console.warn(`No PID found for job ${jobID}, cannot send stop signal`);
  }

  return NextResponse.json(updatedJob);
}
