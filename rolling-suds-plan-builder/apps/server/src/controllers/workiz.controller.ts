import type { Request, Response } from 'express';
import { prisma } from '../config/db.js';
import { workizService } from '../services/workiz.js';

export async function listWorkizAppointments(req: Request, res: Response) {
  const q = req.query.q?.toString();
  const rows = await workizService.listEstimateAppointments(q);
  res.json(rows);
}

export async function importWorkizAppointment(req: Request, res: Response) {
  const { appointmentId } = req.params;
  const payload = await workizService.getAppointmentBundle(appointmentId);
  if (!payload) return res.status(404).json({ message: 'Appointment not found in Workiz adapter' });

  const [firstName, ...lastParts] = payload.customerName.split(' ');
  const customer = await prisma.customer.create({
    data: {
      firstName,
      lastName: lastParts.join(' ') || 'Unknown',
      phone: payload.phone,
      externalSource: 'WORKIZ',
      externalCustomerId: payload.customerId
    }
  });

  const property = await prisma.property.create({
    data: {
      customerId: customer.id,
      serviceAddress: payload.address,
      city: 'Charlotte',
      state: 'NC',
      zip: '28207',
      externalSource: 'WORKIZ',
      externalPropertyId: payload.propertyId
    }
  });

  const appointment = await prisma.appointment.create({
    data: {
      customerId: customer.id,
      propertyId: property.id,
      appointmentType: 'Estimate',
      scheduledStart: new Date(payload.scheduledStart),
      status: payload.status,
      externalSource: 'WORKIZ',
      externalAppointmentId: payload.appointmentId,
      rawExternalPayload: payload
    }
  });

  const estimate = await prisma.estimate.create({
    data: {
      customerId: customer.id,
      propertyId: property.id,
      appointmentId: appointment.id,
      subtotal: payload.lineItems.reduce((sum, l) => sum + l.total, 0),
      tax: 0,
      totalPrice: payload.lineItems.reduce((sum, l) => sum + l.total, 0),
      status: 'draft',
      externalSource: 'WORKIZ',
      externalEstimateId: payload.estimateId,
      externalJobId: payload.jobId,
      rawExternalPayload: payload,
      lineItems: {
        create: payload.lineItems.map((line, idx) => ({
          serviceName: line.name,
          quantity: line.qty,
          unitPrice: line.unitPrice,
          totalPrice: line.total,
          sortOrder: idx,
          externalSource: 'WORKIZ',
          externalLineItemId: line.id
        }))
      }
    },
    include: { lineItems: true }
  });

  const assessment = await prisma.assessment.create({
    data: {
      customerId: customer.id,
      propertyId: property.id,
      appointmentId: appointment.id,
      estimateId: estimate.id,
      createdByUserId: req.body.userId,
      reportType: 'residential',
      title: `Property Cleaning Plan - ${payload.customerName}`,
      sourceImportedFromWorkiz: true,
      overallSummary: 'Imported from Workiz estimate appointment.'
    }
  });

  await prisma.workizSyncLog.create({
    data: {
      entityType: 'appointment_bundle',
      externalId: payload.appointmentId,
      syncDirection: 'import',
      syncStatus: 'success',
      payloadSnapshot: payload
    }
  });

  res.status(201).json({ customer, property, appointment, estimate, assessment });
}
