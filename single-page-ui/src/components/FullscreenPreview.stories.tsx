import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import FullscreenPreview from './FullscreenPreview';

const meta: Meta<typeof FullscreenPreview> = {
  title: 'Components/FullscreenPreview',
  component: FullscreenPreview,
  tags: ['autodocs'],
  argTypes: {
    onClose: { action: 'closed' },
  },
};

export default meta;
type Story = StoryObj<typeof FullscreenPreview>;

export const Default: Story = {
  args: {
    src: 'https://placehold.co/800x600/1a1a2e/ffffff?text=Sample+Image',
    alt: 'Sample image',
    onClose: () => {},
  },
};
