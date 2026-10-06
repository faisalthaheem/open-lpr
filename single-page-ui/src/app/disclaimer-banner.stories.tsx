import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import DisclaimerBanner from './disclaimer-banner';

const meta: Meta<typeof DisclaimerBanner> = {
  title: 'Components/DisclaimerBanner',
  component: DisclaimerBanner,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof DisclaimerBanner>;

export const Default: Story = {};

/**
 * Dismissal is now component state rather than a persisted localStorage flag,
 * so this clicks the control instead of seeding storage. The previous version
 * set `lpr-disclaimer-dismissed`, which nothing reads any more -- and which
 * suppressed the notice permanently for anyone who had ever dismissed it.
 */
export const Dismissed: Story = {
  play: async ({ canvasElement }) => {
    canvasElement.querySelector<HTMLButtonElement>('button[aria-label="Dismiss"]')?.click();
  },
};
