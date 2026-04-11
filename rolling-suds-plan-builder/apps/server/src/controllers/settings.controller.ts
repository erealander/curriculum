import type { Request, Response } from 'express';
import { prisma } from '../config/db.js';

export async function getSettings(_: Request, res: Response) {
  const row = await prisma.setting.findFirst();
  res.json(row);
}

export async function upsertSettings(req: Request, res: Response) {
  const existing = await prisma.setting.findFirst();
  if (existing) {
    const row = await prisma.setting.update({ where: { id: existing.id }, data: req.body });
    return res.json(row);
  }
  const row = await prisma.setting.create({ data: req.body });
  return res.status(201).json(row);
}
