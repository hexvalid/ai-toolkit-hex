import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { getDatasetsRoot } from '@/server/settings';

const resolveDatasetPath = async (name: string) => {
  const datasetsPath = path.resolve(await getDatasetsRoot());
  const datasetPath = path.resolve(datasetsPath, name);

  const relativePath = path.relative(datasetsPath, datasetPath);
  if (
    relativePath === '' ||
    relativePath.startsWith('..') ||
    path.isAbsolute(relativePath)
  ) {
    throw new Error('Invalid dataset path');
  }

  return datasetPath;
};

const deleteDatasetHandler = async (request: Request) => {
  try {
    const body = await request.json();
    const { name } = body;

    if (typeof name !== 'string' || name.trim() === '') {
      return NextResponse.json({ error: 'Dataset name is required' }, { status: 400 });
    }

    const datasetPath = await resolveDatasetPath(name);

    if (!fs.existsSync(datasetPath)) {
      return NextResponse.json({ success: true });
    }

    fs.rmSync(datasetPath, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to delete dataset' }, { status: 500 });
  }
};

export async function POST(request: Request) {
  return deleteDatasetHandler(request);
}

export async function DELETE(request: Request) {
  return deleteDatasetHandler(request);
}
