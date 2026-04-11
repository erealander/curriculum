export type WorkizAppointment = {
  appointmentId: string;
  customerName: string;
  phone?: string;
  address: string;
  scheduledStart: string;
  status: string;
};

export type Tag = { id: string; name: string; category: string; color?: string };
