import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import ImageCard from './ImageCard';
import { mockImageSummaryCompleted, mockImageSummaryFailed, mockImageSummaryPending } from '@/lib/mock-data';

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

export const Failed: Story = {
  args: { image: mockImageSummaryFailed },
};

export const Pending: Story = {
  args: { image: mockImageSummaryPending },
};
