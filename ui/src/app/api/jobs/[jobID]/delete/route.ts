import { NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import { getTrainingFolder } from '@/server/settings';
import path from 'path';
import fs from 'fs';

const prisma = new PrismaClient();

const getJobTrainingFolder = async (job: { job_config: string }) => {
  try {
    const jobConfig = JSON.parse(job.job_config);
    const trainingFolder = jobConfig?.config?.process?.[0]?.training_folder;
    if (typeof trainingFolder === 'string' && trainingFolder.trim() !== '') {
      return path.resolve(trainingFolder);
    }
  } catch {
    // Fall back to the global setting below if the stored config cannot be parsed.
  }

  return path.resolve(await getTrainingFolder());
};

const deleteJobHandler = async ({ params }: { params: Promise<{ jobID: string }> }) => {
  const { jobID } = await params;

  const job = await prisma.job.findUnique({
    where: { id: jobID },
  });

  if (!job) {
    return NextResponse.json({ error: 'Job not found' }, { status: 404 });
  }

  const trainingRoot = await getJobTrainingFolder(job);
  const trainingFolder = path.join(trainingRoot, job.name);

  if (fs.existsSync(trainingFolder)) {
    fs.rmSync(trainingFolder, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
  }

  await prisma.job.delete({
    where: { id: jobID },
  });

  return NextResponse.json(job);
};

export async function DELETE(_request: Request, context: { params: Promise<{ jobID: string }> }) {
  return deleteJobHandler(context);
}

export async function GET(_request: Request, context: { params: Promise<{ jobID: string }> }) {
  return deleteJobHandler(context);
}
