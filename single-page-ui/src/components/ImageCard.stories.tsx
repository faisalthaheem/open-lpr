import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import ImageCard from './ImageCard';
import { mockImageSummaryCompleted, mockImageSummaryFailed, mockImageSummaryPending } from '@/lib/mock-data';
import type { ImageSummary } from '@/lib/api';

const meta: Meta<typeof ImageCard> = {
  title: 'Components/ImageCard',
  component: ImageCard,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof ImageCard>;

export const Completed: Story = {
  args: { image: mockImageSummaryCompleted },
};

export const CompletedMultiplePlates: Story = {
  args: {
    image: {
      ...mockImageSummaryCompleted,
      id: 4,
      plate_count: 2,
      ocr_count: 3,
      first_ocr_text: null,
    } satisfies ImageSummary,
  },
};

export const CompletedZeroPlates: Story = {
  args: {
    image: {
      ...mockImageSummaryCompleted,
      id: 5,
      plate_count: 0,
      ocr_count: 0,
      first_ocr_text: null,
    } satisfies ImageSummary,
  },
};

export const Failed: Story = {
  args: { image: mockImageSummaryFailed },
};

export const Pending: Story = {
  args: { image: mockImageSummaryPending },
};
