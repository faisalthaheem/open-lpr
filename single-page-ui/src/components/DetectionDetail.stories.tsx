import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import DetectionDetail from './DetectionDetail';
import { mockDetection, mockDetectionMultiplePlates } from '@/lib/mock-data';

const meta: Meta<typeof DetectionDetail> = {
  title: 'Components/DetectionDetail',
  component: DetectionDetail,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof DetectionDetail>;

export const SinglePlate: Story = {
  args: {
    detections: { detections: [mockDetection] },
  },
};

export const MultiplePlates: Story = {
  args: {
    detections: { detections: mockDetectionMultiplePlates },
  },
};

export const NoDetections: Story = {
  args: {
    detections: { detections: [] },
  },
};

export const NullData: Story = {
  args: {
    detections: null,
  },
};
