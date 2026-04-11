import PDFDocument from 'pdfkit';
import type { Assessment, Customer, Photo, PricingOption, Property, SurfaceObservation } from '@prisma/client';

export function buildAssessmentPdf(data: {
  branding: { companyName: string; footerText?: string; primaryColor?: string };
  assessment: Assessment;
  customer: Customer;
  property: Property;
  observations: SurfaceObservation[];
  pricing: PricingOption[];
  photos: Photo[];
}) {
  const doc = new PDFDocument({ margin: 48 });
  const buffers: Uint8Array[] = [];
  doc.on('data', (c) => buffers.push(c));

  doc.fontSize(24).fillColor(data.branding.primaryColor ?? '#0f3d4c').text(data.branding.companyName);
  doc.moveDown(0.2);
  doc.fontSize(16).fillColor('#111').text(data.assessment.title);
  doc.moveDown();

  doc.fontSize(10).fillColor('#333').text(`${data.customer.firstName} ${data.customer.lastName}`);
  doc.text(data.property.serviceAddress);
  doc.text(`${data.property.city}, ${data.property.state} ${data.property.zip}`);

  doc.moveDown();
  doc.fontSize(12).text('Assessment Summary', { underline: true });
  doc.fontSize(10).text(data.assessment.overallSummary ?? 'No summary provided');

  doc.moveDown();
  doc.fontSize(12).text('Surface Observations', { underline: true });
  data.observations.forEach((obs) => {
    doc.moveDown(0.5);
    doc.fontSize(11).text(obs.surfaceType);
    doc.fontSize(10).text(`Condition: ${obs.conditionObserved ?? 'N/A'}`);
    doc.text(`Cause: ${obs.likelyCause ?? 'N/A'}`);
    doc.text(`Recommended method: ${obs.recommendedMethod ?? 'TBD on site'}`);
    doc.text(`Notes: ${obs.notes ?? 'None'}`);
  });

  doc.moveDown();
  doc.fontSize(12).text('Investment Options', { underline: true });
  data.pricing.forEach((p) => doc.fontSize(10).text(`${p.packageName} - $${p.price.toString()} (${p.description ?? ''})`));

  if (data.assessment.exclusions) {
    doc.moveDown();
    doc.fontSize(12).text('Exclusions & Expectations', { underline: true });
    doc.fontSize(10).text(data.assessment.exclusions);
  }

  doc.moveDown();
  doc.fontSize(9).fillColor('#666').text(data.branding.footerText ?? 'Prepared by Rolling Suds');
  doc.end();

  return new Promise<Buffer>((resolve) => {
    doc.on('end', () => resolve(Buffer.concat(buffers)));
  });
}
