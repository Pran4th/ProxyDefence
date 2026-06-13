import { Suspense, lazy } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/ProtectedRoute";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/context/AuthContext";

const Landing = lazy(() => import("./pages/Landing"));
const About = lazy(() => import("./pages/About"));
const News = lazy(() => import("./pages/News"));
const Auth = lazy(() => import("./pages/Auth"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Simulations = lazy(() => import("./pages/Simulations"));
const Profile = lazy(() => import("./pages/Profile"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Events = lazy(() => import("./pages/Events"));
const EventDetails = lazy(() => import("./pages/EventDetails"));
const Entities = lazy(() => import("./pages/Entities"));
const EntityDetails = lazy(() => import("./pages/EntityDetails"));
const Search = lazy(() => import("./pages/Search"));
const Copilot = lazy(
  () => import("./pages/Copilot")
);
const Briefings = lazy(
  () => import("./pages/Briefings")
);
const queryClient = new QueryClient();

const RouteLoader = () => (
  <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
    <div className="text-center">
      <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-b-2 border-primary" />
      <p className="text-sm uppercase tracking-[0.28em]">Loading workspace</p>
    </div>
  </div>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Suspense fallback={<RouteLoader />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/about" element={<About />} />
              <Route path="/news" element={<News />} />
              <Route path="/auth" element={<Auth />} />
              <Route
                path="/dashboard"
                element={(
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                )}
              />
              <Route
                path="/analytics"
                element={(
                  <ProtectedRoute>
                    <Analytics />
                  </ProtectedRoute>
                )}
              />
              <Route
                path="/simulations"
                element={(
                  <ProtectedRoute>
                    <Simulations />
                  </ProtectedRoute>
                )}
              />
              <Route
                path="/profile"
                element={(
                  <ProtectedRoute>
                    <Profile />
                  </ProtectedRoute>
                )}
              />
              <Route
                path="/entities"
                element={
                  <ProtectedRoute>
                     <Entities />
                  </ProtectedRoute>
              }
              />
              <Route
                path="/entities/:entityName"
                element={
                  <ProtectedRoute>
                     <EntityDetails />
                  </ProtectedRoute>
              }
              />
              <Route
                path="/events"
                element={
                <ProtectedRoute>
                   <Events />
                </ProtectedRoute>
              }
              />
              <Route
                path="/events/:eventId"
                element={
               <ProtectedRoute>
                   <EventDetails />
               </ProtectedRoute>
              }
              />
              <Route
                path="/search"
                element={
              <ProtectedRoute>
                    <Search />
              </ProtectedRoute>
              }
              />
              <Route
                path="/copilot"
                element={
              <ProtectedRoute>
                      <Copilot />
              </ProtectedRoute>
              }
              />
              <Route
                path="/briefings"
                element={
              <ProtectedRoute>
                      <Briefings />
              </ProtectedRoute>
             }
            />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
