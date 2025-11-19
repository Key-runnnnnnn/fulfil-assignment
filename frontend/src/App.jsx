import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Upload from "./pages/Upload";
import Products from "./pages/Products";
import Webhooks from "./pages/Webhooks";

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <Routes>
          <Route path="/" element={<Upload />} />
          <Route path="/products" element={<Products />} />
          <Route path="/webhooks" element={<Webhooks />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
