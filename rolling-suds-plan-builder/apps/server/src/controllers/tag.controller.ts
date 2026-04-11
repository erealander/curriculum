import type { Request, Response } from 'express';
import { prisma } from '../config/db.js';

export async function listTags(req: Request, res: Response) {
  const q = req.query.q?.toString();
  const rows = await prisma.tag.findMany({
    where: q ? { name: { contains: q, mode: 'insensitive' } } : undefined,
    orderBy: { name: 'asc' }
  });
  res.json(rows);
}

export async function createTag(req: Request, res: Response) {
  const tag = await prisma.tag.create({ data: { ...req.body, isSystem: false, category: req.body.category ?? 'custom' } });
  res.status(201).json(tag);
}
