import { env } from '../config/env.js';

type WorkizAppointment = {
  appointmentId: string;
  customerId: string;
  propertyId: string;
  estimateId: string;
  jobId?: string;
  customerName: string;
  phone?: string;
  address: string;
  scheduledStart: string;
  status: string;
  lineItems: Array<{ id: string; name: string; qty: number; unitPrice: number; total: number }>;
};

export interface WorkizService {
  listEstimateAppointments(query?: string): Promise<WorkizAppointment[]>;
  getAppointmentBundle(appointmentId: string): Promise<WorkizAppointment | null>;
}

class MockWorkizService implements WorkizService {
  private readonly demo: WorkizAppointment[] = [
    {
      appointmentId: 'wkz_appt_1001',
      customerId: 'wkz_cust_500',
      propertyId: 'wkz_prop_500',
      estimateId: 'wkz_est_777',
      jobId: 'wkz_job_777',
      customerName: 'Madison Harper',
      phone: '555-0108',
      address: '1489 Briarwood Ln, Charlotte, NC 28207',
      scheduledStart: new Date().toISOString(),
      status: 'scheduled',
      lineItems: [
        { id: 'li_1', name: 'House wash', qty: 1, unitPrice: 725, total: 725 },
        { id: 'li_2', name: 'Patio cleaning', qty: 1, unitPrice: 275, total: 275 }
      ]
    }
  ];

  async listEstimateAppointments(query?: string) {
    if (!query) return this.demo;
    const q = query.toLowerCase();
    return this.demo.filter((a) => [a.customerName, a.address, a.phone, a.appointmentId].join(' ').toLowerCase().includes(q));
  }

  async getAppointmentBundle(appointmentId: string) {
    return this.demo.find((d) => d.appointmentId === appointmentId) ?? null;
  }
}

class ApiWorkizService implements WorkizService {
  async listEstimateAppointments(): Promise<WorkizAppointment[]> {
    // TODO: production Workiz API integration
    // Implement endpoint mappings for appointments/customers/properties/estimates.
    return [];
  }
  async getAppointmentBundle(): Promise<WorkizAppointment | null> {
    return null;
  }
}

export const workizService: WorkizService = env.WORKIZ_MODE === 'api' ? new ApiWorkizService() : new MockWorkizService();
