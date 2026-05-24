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

export const Dismissed: Story = {
  decorators: [
    (Story) => {
      localStorage.setItem('lpr-disclaimer-dismissed', '1');
      return <Story />;
    },
  ],
};
