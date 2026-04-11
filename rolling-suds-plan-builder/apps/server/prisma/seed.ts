import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

const concernTags = [
  'Organic growth','Algae','Mold / mildew','Oxidation risk','Tiger striping','Rust staining','Efflorescence','Oil staining','Heavy soiling','Water intrusion risk','Delicate paint','Aging finish','Access constraints','Landscaping sensitivity','Loose caulk','Compromised seals','Shaded-side buildup','Surface etching risk','Paint failure','Grease buildup','Slip hazard','Drainage issue','Embedded dirt','Post-construction dust','Cobweb buildup','Heavy pollen','Black streaking','Mildew spotting'
];
const serviceTags = ['House wash','Roof wash','Roof treatment','Exterior gutter wash','Gutter brightening','Interior gutter cleanout','Patio cleaning','Walkway cleaning','Driveway cleaning'];
const methodTags = ['Soft wash','Low-pressure rinse','Downstream application','Surface cleaner','Hot water cleaning','Manual agitation','Spot treatment','Specialty restoration','Post-treatment rinse','Method to be confirmed on site'];
const limitationTags = ['Oxidation not included','Interior gutter cleanout not included','Rust removal not included','Paint correction not included','Stain reduction may vary','Final results depend on surface age/condition'];

async function main() {
  const passwordHash = await bcrypt.hash('rolling123!', 10);
  const user = await prisma.user.upsert({
    where: { email: 'estimator@rollingsuds.com' },
    update: {},
    create: { name: 'Lead Estimator', email: 'estimator@rollingsuds.com', passwordHash, role: 'admin' }
  });

  const allTags = [
    ...concernTags.map((name) => ({ name, category: 'concern' as const })),
    ...serviceTags.map((name) => ({ name, category: 'service' as const })),
    ...methodTags.map((name) => ({ name, category: 'method' as const })),
    ...limitationTags.map((name) => ({ name, category: 'limitation' as const }))
  ];

  for (const t of allTags) {
    await prisma.tag.upsert({ where: { name: t.name }, update: {}, create: { ...t, isSystem: true } });
  }

  const customer = await prisma.customer.create({ data: { firstName: 'Madison', lastName: 'Harper', email: 'madison@example.com', phone: '704-555-0108', externalSource: 'WORKIZ', externalCustomerId: 'wkz_cust_500' } });
  const property = await prisma.property.create({ data: { customerId: customer.id, serviceAddress: '1489 Briarwood Ln', city: 'Charlotte', state: 'NC', zip: '28207', propertyType: 'Upscale residential', externalSource: 'WORKIZ', externalPropertyId: 'wkz_prop_500' } });
  const appointment = await prisma.appointment.create({ data: { customerId: customer.id, propertyId: property.id, appointmentType: 'Estimate', scheduledStart: new Date(), status: 'scheduled', assignedRep: 'Lead Estimator', externalSource: 'WORKIZ', externalAppointmentId: 'wkz_appt_1001' } });
  const estimate = await prisma.estimate.create({ data: { customerId: customer.id, propertyId: property.id, appointmentId: appointment.id, subtotal: 1000, tax: 0, totalPrice: 1000, status: 'draft', externalSource: 'WORKIZ', externalEstimateId: 'wkz_est_777', externalJobId: 'wkz_job_777' } });

  await prisma.estimateLineItem.createMany({ data: [
    { estimateId: estimate.id, serviceName: 'House wash', description: 'Soft wash all siding elevations', quantity: 1, unitPrice: 725, totalPrice: 725, sortOrder: 1, externalSource: 'WORKIZ', externalLineItemId: 'li_1' },
    { estimateId: estimate.id, serviceName: 'Patio cleaning', description: 'Surface clean rear patio and rinse', quantity: 1, unitPrice: 275, totalPrice: 275, sortOrder: 2, externalSource: 'WORKIZ', externalLineItemId: 'li_2' }
  ]});

  const assessment = await prisma.assessment.create({
    data: {
      customerId: customer.id,
      propertyId: property.id,
      appointmentId: appointment.id,
      estimateId: estimate.id,
      createdByUserId: user.id,
      reportType: 'residential',
      title: 'Rolling Suds Property Cleaning Plan',
      overallSummary: 'Upscale residence with visible north-side algae, tiger striping at gutters, and patio soiling. Recommended soft house wash and patio cleaning with careful downstream application.',
      recommendedScope: 'House wash + patio cleaning',
      processDescription: 'Soft wash application with low-pressure rinse. Final method confirmed on site.',
      limitationsExpectations: 'Final results depend on surface age/condition. Stain reduction may vary.',
      exclusions: 'Oxidation restoration not included. Interior gutter cleanout not included.',
      sourceImportedFromWorkiz: true
    }
  });

  await prisma.surfaceObservation.createMany({ data: [
    { assessmentId: assessment.id, surfaceType: 'Siding (north elevation)', conditionObserved: 'Algae buildup and mildew spotting', likelyCause: 'Persistent shade and moisture retention', recommendedMethod: 'Soft wash', severity: 'Moderate', notes: 'Visible streaking near downspouts and trim.', inputMode: 'mixed', sortOrder: 1 },
    { assessmentId: assessment.id, surfaceType: 'Gutters', conditionObserved: 'Tiger striping and heavy pollen', likelyCause: 'Electrostatic bonding + runoff patterning', recommendedMethod: 'Spot treatment + low-pressure rinse', severity: 'Moderate', notes: 'Brightening may improve appearance but full restoration excluded.', inputMode: 'typed', sortOrder: 2 },
    { assessmentId: assessment.id, surfaceType: 'Rear patio', conditionObserved: 'Heavy soiling and embedded dirt', likelyCause: 'High foot traffic and organic debris', recommendedMethod: 'Surface cleaner + post-treatment rinse', severity: 'High', notes: 'Potential slip hazard when wet.', inputMode: 'dictated', sortOrder: 3 }
  ]});

  await prisma.pricingOption.createMany({ data: [
    { assessmentId: assessment.id, packageName: 'Good', serviceName: 'House wash', description: 'Core siding wash and rinse', price: 725, included: true, sortOrder: 1 },
    { assessmentId: assessment.id, packageName: 'Better', serviceName: 'House wash + patio cleaning', description: 'Adds patio cleaning and post-treatment rinse', price: 1000, included: true, sortOrder: 2 },
    { assessmentId: assessment.id, packageName: 'Best', serviceName: 'Full exterior refresh', description: 'Adds gutter exterior wash and prioritized spot treatment', price: 1260, included: true, sortOrder: 3 }
  ]});

  await prisma.setting.create({ data: { companyName: 'Rolling Suds Property Cleaning', phone: '(704) 555-0199', email: 'hello@rollingsuds.com', website: 'https://rollingsuds.com', address: 'Charlotte, NC', primaryColor: '#123647', secondaryColor: '#2f9eb5', footerText: 'Thank you for choosing Rolling Suds. Final method confirmed on site.' } });
}

main().finally(async () => {
  await prisma.$disconnect();
});
