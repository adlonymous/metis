import { createRoot } from 'react-dom/client';
import { DatasetEditor } from './dataset-editor';
import './editor.css';

const root = document.getElementById('root');
if (!root) throw new Error('Metis editor root element is missing');
createRoot(root).render(<DatasetEditor />);
