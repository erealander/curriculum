import type { Request, Response } from 'express';
import { prisma } from '../config/db.js';
import { buildAssessmentPdf } from '../utils/pdf.js';

export async function getAssessment(req: Request, res: Response) {
  const assessment = await prisma.assessment.findUnique({
    where: { id: req.params.id },
    include: {
      customer: true,
      property: true,
      observations: { include: { tags: { include: { tag: true } } }, orderBy: { sortOrder: 'asc' } },
      pricingOptions: { orderBy: { sortOrder: 'asc' } },
      photos: { orderBy: { sortOrder: 'asc' } }
    }
  });
  if (!assessment) return res.status(404).json({ message: 'Not found' });
  res.json(assessment);
}

export async function upsertObservation(req: Request, res: Response) {
  const body = req.body;
  const row = await prisma.surfaceObservation.upsert({
    where: { id: body.id ?? 'missing' },
    update: {
      surfaceType: body.surfaceType,
      conditionObserved: body.conditionObserved,
      likelyCause: body.likelyCause,
      recommendedMethod: body.recommendedMethod,
      severity: body.severity,
      includedInScope: body.includedInScope,
      notes: body.notes,
      inputMode: body.inputMode,
      sortOrder: body.sortOrder
    },
    create: {
      assessmentId: body.assessmentId,
      surfaceType: body.surfaceType,
      conditionObserved: body.conditionObserved,
      likelyCause: body.likelyCause,
      recommendedMethod: body.recommendedMethod,
      severity: body.severity,
      includedInScope: body.includedInScope ?? true,
      notes: body.notes,
      inputMode: body.inputMode ?? 'mixed',
      sortOrder: body.sortOrder ?? 0
    }
  });

  if (Array.isArray(body.tagIds)) {
    await prisma.observationTag.deleteMany({ where: { observationId: row.id } });
    await prisma.observationTag.createMany({ data: body.tagIds.map((tagId: string) => ({ observationId: row.id, tagId })) });
  }

  res.json(row);
}

export async function updateAssessment(req: Request, res: Response) {
  const row = await prisma.assessment.update({ where: { id: req.params.id }, data: req.body });
  res.json(row);
}

export async function createPdf(req: Request, res: Response) {
  const record = await prisma.assessment.findUnique({
    where: { id: req.params.id },
    include: { customer: true, property: true, observations: true, pricingOptions: true, photos: true }
  });
  if (!record) return res.status(404).json({ message: 'Not found' });

  const branding = await prisma.setting.findFirst();
  const pdf = await buildAssessmentPdf({
    branding: {
      companyName: branding?.companyName ?? 'Rolling Suds Property Cleaning',
      primaryColor: branding?.primaryColor ?? '#123647',
      footerText: branding?.footerText ?? undefined
    },
    assessment: record,
    customer: record.customer,
    property: record.property,
    observations: record.observations,
    pricing: record.pricingOptions,
    photos: record.photos
  });

  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', `attachment; filename=${record.id}.pdf`);
  res.send(pdf);
}
