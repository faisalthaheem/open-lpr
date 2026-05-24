import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import UploadForm from './UploadForm';

const meta: Meta<typeof UploadForm> = {
  title: 'Components/UploadForm',
  component: UploadForm,
  tags: ['autodocs'],
  argTypes: {
    onSuccess: { action: 'success' },
    onError: { action: 'error' },
  },
};

export default meta;
type Story = StoryObj<typeof UploadForm>;

export const Default: Story = {};
